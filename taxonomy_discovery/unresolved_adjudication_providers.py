"""Explicit evaluation transports. No provider is initialized on import.

Cloud reservations are durable, shared and conservative; uncertainty stops
the experiment. This is not an account-wide provider billing guarantee.
"""
from contextlib import contextmanager
from decimal import Decimal, ROUND_CEILING
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import urllib.request
import uuid

from taxonomy_discovery.unresolved_adjudication import fingerprint

MODELS = {'gpt-5.6-luna': ('0.20', '1.20'), 'gpt-5.4-mini': ('0.75', '4.50')}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _read_json(response):
    data = response.read(128001)
    if len(data) > 128000:
        raise ValueError('Provider response exceeded bound')
    return json.loads(data)


def ollama_transport(prompt, model):
    """Fixed loopback endpoint, serial request, no cloud fallback or retries."""
    payload = {'model': model, 'prompt': prompt, 'stream': False, 'format': 'json',
        'think': False, 'options': {'temperature': 0, 'num_predict': 1600, 'num_ctx': 8192}}
    request = urllib.request.Request('http://127.0.0.1:11434/api/generate',
        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    # Ignore environment proxy settings for the local-only endpoint.
    with urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect()).open(request, timeout=180) as response:
        result = _read_json(response)
    return {'text': result['response'], 'model_snapshot': result.get('digest'),
        'usage': {'input_tokens': result.get('prompt_eval_count'), 'output_tokens': result.get('eval_count')}}


def pricing(model, configuration):
    if model not in MODELS or not configuration or configuration.get('model') != model:
        raise ValueError('Explicit supported model and pricing required')
    if (configuration.get('verified') is not True or not configuration.get('verified_at')
            or not str(configuration.get('source', '')).startswith('https://developers.openai.com/')
            or configuration.get('tier') != 'standard'):
        raise ValueError('Fresh official standard-tier pricing confirmation required')
    try:
        verified = datetime.fromisoformat(configuration['verified_at'])
        age = (datetime.now(timezone.utc) - verified).total_seconds()
        if not 0 <= age <= 86400:
            raise ValueError('Pricing verification expired')
        rates = [Decimal(str(configuration.get(k))) for k in ('input_per_million', 'output_per_million')]
    except (ArithmeticError, TypeError, KeyError) as exc:
        raise ValueError('Invalid pricing verification') from exc
    if any(not r.is_finite() or r < Decimal(floor) for r, floor in zip(rates, MODELS[model])):
        raise ValueError('Uncertain/under-reserved rates cannot execute')
    return rates


def preflight(prompts, model, configuration, max_output_tokens=1200):
    rates = pricing(model, configuration)
    if type(max_output_tokens) is not int or not 16 <= max_output_tokens <= 4096:
        raise ValueError('Bounded total output token limit required')
    requests = []
    for prompt in prompts:
        # Conservative one token per UTF-8 byte plus framing headroom. Fixed
        # text-only input; no tools, files, multimodal inputs or discounts.
        input_bound = len(prompt.encode('utf-8')) + 1024
        if input_bound > 16000:
            raise ValueError('Compact short-context bound exceeded')
        # Extra input headroom covers framing/cache-write uncertainty; never
        # assume a cache/batch/flex discount when reserving standard pricing.
        cost = (rates[0] * input_bound * 3 + rates[1] * max_output_tokens) / Decimal(1000000)
        requests.append({'input_token_upper_bound': input_bound, 'max_output_tokens': max_output_tokens,
            'reserved_nanousd': int((cost * Decimal(1000000000)).to_integral_value(rounding=ROUND_CEILING)),
            'prompt_fingerprint': fingerprint(prompt)})
    return {'model': model, 'pricing': configuration, 'requests': requests,
        'worst_case_usd': sum(r['reserved_nanousd'] for r in requests) / 1e9,
        'preflight_id': fingerprint({'requests': requests, 'model': model, 'pricing': configuration})}


class ExperimentLedger:
    """One immutable experiment identity/ceiling across models and resumptions."""
    def __init__(self, path, experiment_id, case_fingerprint, ceiling=.50):
        self.path = Path(path)
        if self.path.suffix != '.json' or not experiment_id or not case_fingerprint:
            raise ValueError('Explicit experiment JSON ledger and case identity required')
        value = Decimal(str(ceiling))
        if not value.is_finite() or not 0 < value <= Decimal('.50'):
            raise ValueError('Shared budget ceiling must be at most US$0.50')
        self.identity = {'experiment_id': experiment_id, 'case_fingerprint': case_fingerprint,
            'ceiling_nanousd': int(value * Decimal(1000000000))}

    @contextmanager
    def locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_suffix('.lock')
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding='utf-8'))
                seal = data.pop('fingerprint')
                if fingerprint(data) != seal or data['identity'] != self.identity:
                    raise ValueError('Ledger identity/integrity mismatch; budget cannot reset')
            else:
                data = {'identity': self.identity, 'requests': []}
            yield data
        finally:
            os.close(fd); lock.unlink()

    def save(self, data):
        payload = {**data, 'fingerprint': fingerprint(data)}
        temp = self.path.with_suffix('.pending')
        temp.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        os.replace(temp, self.path)

    def execute(self, reservation, model, consent_id, call, rates):
        with self.locked() as data:
            if any(r['status'] != 'metered' for r in data['requests']):
                raise ValueError('Ambiguous reservation requires human reconciliation')
            used = sum(r['charged_nanousd'] for r in data['requests'])
            if reservation['reserved_nanousd'] + used > self.identity['ceiling_nanousd']:
                raise ValueError('Shared budget exhausted before transport')
            row = {**reservation, 'model': model, 'consent_id': consent_id,
                'experiment_id': self.identity['experiment_id'], 'timestamp': datetime.now(timezone.utc).isoformat(),
                'local_request_id': str(uuid.uuid4()), 'status': 'reserved',
                'charged_nanousd': reservation['reserved_nanousd']}
            data['requests'].append(row); self.save(data)  # reserve before send
            try:
                result = call()
                reported_model = result.get('model')
                if reported_model and reported_model != model and not reported_model.startswith(model + '-'):
                    raise ValueError('Unexpected model/pricing identity')
                if result.get('service_tier') not in (None, 'default', 'standard'):
                    raise ValueError('Unexpected service tier; reservation retained')
                usage = result.get('usage') or {}
                inp, out = usage.get('input_tokens'), usage.get('output_tokens')
                reasoning = (usage.get('output_tokens_details') or {}).get('reasoning_tokens', 0)
                if (any(type(n) is not int or n < 0 for n in (inp, out, reasoning))
                        or reasoning > out or inp > reservation['input_token_upper_bound']
                        or out > reservation['max_output_tokens'] or not isinstance(result.get('id'), str) or not result['id']):
                    raise ValueError('Missing/inconsistent metering; reservation retained')
                observed = (rates[0] * inp + rates[1] * out) * Decimal(1000)
                row.update(status='metered', provider_request_id=result.get('id'),
                    usage={'input_tokens': inp, 'output_tokens': out, 'output_tokens_details': {'reasoning_tokens': reasoning}},
                    observed_nanousd=int(observed.to_integral_value(rounding=ROUND_CEILING)))
                # Do not release worst-case reserves on resumptions; uncertainty
                # cannot create a refund or expand the experiment allowance.
                self.save(data)
                return {'text': result['text'], 'usage': usage, 'model_snapshot': result.get('model'),
                    'cost': deepcopy_safe(row)}
            except Exception:
                row['status'] = 'ambiguous'; self.save(data)
                raise ValueError('Cloud request uncertain; reservation retained, no retry') from None


def deepcopy_safe(value):
    return json.loads(json.dumps(value))


def cloud_transport_factory(*, plan, ledger, consent_id, authorized=False, api_key=None, client=None):
    if plan.get('preflight_id') != fingerprint({k: plan[k] for k in ('requests', 'model', 'pricing')}):
        raise ValueError('Confirmed preflight integrity mismatch')
    if not authorized or consent_id != plan['preflight_id'] or not isinstance(api_key, str) or not api_key.strip():
        raise ValueError('Explicit paid authorization, consent and credential required')
    if client is None and not api_key.startswith('sk-'):
        raise ValueError('Invalid API credential format')
    rates = pricing(plan['model'], plan['pricing'])
    index = 0
    def transport(prompt, model):
        nonlocal index
        if model != plan['model'] or index >= len(plan['requests']):
            raise ValueError('Request outside confirmed preflight')
        reservation = plan['requests'][index]
        if fingerprint(prompt) != reservation['prompt_fingerprint']:
            raise ValueError('Inputs changed since cost/privacy confirmation')
        recalculated = preflight([prompt], model, plan['pricing'], reservation['max_output_tokens'])['requests'][0]
        if recalculated != reservation:
            raise ValueError('Reservation no longer bounds the confirmed request')
        payload = {'model': model, 'input': prompt, 'max_output_tokens': reservation['max_output_tokens'],
            'store': False, 'background': False, 'tools': [], 'service_tier': 'default',
            'text': {'format': {'type': 'json_object'}}}
        def call():
            if client is not None: return client(payload)
            request = urllib.request.Request('https://api.openai.com/v1/responses', data=json.dumps(payload).encode(),
                headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
            with opener.open(request, timeout=90) as response: result = _read_json(response)
            if result.get('status') != 'completed': raise ValueError('Incomplete provider result')
            result['text'] = ''.join(c.get('text', '') for item in result.get('output', [])
                for c in item.get('content', []) if c.get('type') == 'output_text')
            return result
        index += 1  # no retry even on ambiguous error
        return ledger.execute(reservation, model, consent_id, call, rates)
    return transport
