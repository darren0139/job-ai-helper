import sys
import tempfile
import webbrowser

from openai_codex import Codex, Sandbox


MARKER = "CODEX_SMOKE_OK"


def main() -> int:
    # Use an empty temporary directory so this smoke test does not expose the
    # Job AI Helper repository as the Codex working directory.
    with tempfile.TemporaryDirectory(prefix="codex-smoke-") as temp_dir:
        print(f"Temporary working directory: {temp_dir}")

        with Codex() as codex:
            # Check whether the SDK already has a usable Codex/ChatGPT login.
            account = codex.account(refresh_token=False)
            authenticated = getattr(account, "account", None) is not None
            print(f"Authenticated: {authenticated}")

            if not authenticated:
                print("No Codex authentication found.")
                print("Starting ChatGPT browser login...")

                login = codex.login_chatgpt()
                auth_url = getattr(login, "auth_url", None)

                if auth_url:
                    print(f"Open this URL if your browser does not open automatically:\n{auth_url}")
                    webbrowser.open(auth_url)

                # Wait for the SDK to receive the completed login event.
                completion = login.wait()

                print("Login completion:", completion)
                print("Login success:", getattr(completion, "success", None))
                print("Login error:", getattr(completion, "error", None))

                account = codex.account(refresh_token=True)
                print("Account state:", account)

                authenticated = bool(getattr(account, "authenticated", False))
                print(f"Authenticated after login: {authenticated}")

                if not authenticated:
                    print("ERROR: ChatGPT authentication did not complete.")
                    return 1

            print("Starting read-only Codex smoke-test thread...")

            thread = codex.thread_start(
                cwd=temp_dir,
                sandbox=Sandbox.read_only,
                ephemeral=True,
            )

            result = thread.run(
                f"This is a connectivity smoke test. Reply with exactly: {MARKER}",
                sandbox=Sandbox.read_only,
            )

            response = getattr(result, "final_response", None)

            if response is None:
                # Keep the test useful even if this SDK version exposes the
                # result under a different convenience attribute.
                print("Turn completed, but no 'final_response' attribute was found.")
                print("Raw TurnResult:")
                print(result)
                return 2

            print(f"Codex response: {response}")

            if response.strip() != MARKER:
                print(f"WARNING: Expected exactly {MARKER!r}.")
                return 3

            print("SUCCESS: Codex SDK runtime, authentication, and model invocation all worked.")
            return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise
