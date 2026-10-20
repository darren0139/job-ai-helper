# JD metadata ambiguity refinement — experimental v1.23

## Review decision and boundary

Implemented an explicitly invoked refinement, not a production scoring change. The independently specified Job 35 qualification and Job 48 responsibility recoveries pass; administrative exclusions remain protected. Unknown or mixed content is retained for review. Availability is a consequence of classification correctness, not the optimization target.

Repository: `C:/Users/Admin/Documents/GitHub/Job-AI-Helper-Codex-Resolver`; branch `fix/jd-metadata-ambiguity-v1`; checkpoint/HEAD `07912485d4803f355a760f2623a4a08f5b729fa2`. The only entry untracked file was `coordinated_batch_dashboard_review.md`; it is preserved.

Final verification and the three separate readiness decisions are below. No `app.py` integration, default activation, saved-analysis migration, Application Session change, database access, candidate loading, model or network call is introduced.

## Root cause and bounded rules

The earlier raw-JD metadata leak and v1.22's conservative correction remain reproducible. `_raw_jd_content_spans` tracks exact/inferred section boundaries; `_raw_jd_requirement_rows` admits content from active scoring sections; `_requirement_sources` controls profile/raw authority; `canonicalise_requirements` assigns identities, merges and allocations. None of the native matching, evidence ranking, ownership or credit policies is redesigned here.

`jd_metadata_policy.classify` in v1.22 treats unrecognized short colon headings as uncertain boundaries, resets scoring context, and treats every subsequent unsupported line as ambiguous. Its builder withholds aggregates for any ambiguous content. This does not distinguish `Skillset:` or a responsibility-list introducer from genuinely unknown administrative text. Separately, unheaded titles, employer descriptions, contract duration and duplicate posting values can create unnecessary blocking receipts. These are structural/admission issues, before evidence evaluation; native NONE is not proof that classification is correct.

The new `jd_metadata_v123.classify` starts from an unmodified v1.22 receipt and applies these finite rules:

1. **Corroborated candidate lists.** Exact qualification introducers (`Skillset`, `Candidate skillset`, `Additional qualifications include`) require at least two locally supported qualification children. Exact responsibility introducers (`Other responsibilities include`, `Additional responsibilities include`) require at least two imperative duty children. The introducer is structural, never a requirement. Child support is bounded to candidate qualification forms and duty verbs; a heading by itself does not admit arbitrary technology names.
2. **Unfamiliar headings.** A previously unknown colon heading may recover a qualification list only with a previously verified required/core/preferred section and at least two consistently qualifying local children. Administrative boundaries clear that inherited authority. An unknown heading without this support cannot authorize scoring. Explicit independently grounded obligations retain native handling even if their heading remains unfamiliar.
3. **Importance and original source.** A recovered list inherits a verified parent qualification heading for its existing required/preferred importance. New structural receipts record the actual introducer and supporting children. The native parser receives an optional section override only in the new context; original raw text, line numbers and source-parent identities remain authoritative. Wrapped/indented candidate children use the existing native grouping and duplicate-allocation machinery.
4. **Posting information.** Existing field/value and weekday/clock exclusions remain. The finite anchored field vocabulary additionally recognizes `Position`, `Working Location` and `Salary Range`. Explicit contract-duration/shortlisting-notification wording is administrative. A compound contract statement containing a candidate obligation stays unresolved. Unheaded duplicates of independently identified administrative values are linked to that original field receipt, not classified by a global word blacklist.
5. **High-confidence harmless context.** Short unheaded role titles and bounded organisation/role-purpose descriptions without candidate-obligation cues can be excluded without withholding. This is not a general employer-prose classifier. Descriptions containing candidate cues, mixed role/recruiting prose and unsupported heading variants remain reviewable rather than being forced into context or qualifications.
6. **Administrative boundary safety.** An administrative occurrence terminates inherited scoring-section admission. Later candidate content must be independently admissible or acquire a new corroborated candidate heading. Otherwise it receives an unresolved receipt; it is not silently dropped to produce a partial numeric score. Blank lines do not cancel that boundary. A generic invitation to apply does not establish a new technical qualification.

The explicit withholding threshold is **one or more unresolved content classifications, an empty admitted requirement set, or any existing coordinated-action REVIEW_REQUIRED outcome**. Administrative/context exclusions and structural headings resolved with high confidence do not themselves withhold. Uncertain text is not assigned a fabricated numeric NONE/DIRECT result. Whole-JD alignment, coverage, evidence strength, band and boundary status stay null when withheld; no partial normalized score is published.

## Independent expectations and complete source audit

Two new fixtures are separate from classifier output and all historical scoring oracles:

- `tests/fixtures/jd_metadata_v123_expectations.json` records the exact Job 35/48 source text, structural versus candidate decisions and independent justifications, plus the Job 45/359 administrative controls.
- `tests/fixtures/jd_metadata_v123_span_review.json` records analyst judgments for all **83** original ambiguous source lines across **19** packets, with exact job/line/text references. These are independently authored expectations for human review, not a claim that the user approved them. An analyst judgment that a line describes a genuine duty does not authorize an unimplemented general detector to admit it automatically.

[The complete span audit](jd_metadata_v123_span_audit.md) reports every original ambiguous line and eight additional boundary controls: full original text, line number, zero-based/end-exclusive character offsets, adjacent lines and section context, original native spans/admitted rows, v1.22 decision/reason, independent assessment, proposed v1.23 decision/reason, per-version parent IDs/importance/allocation and packet availability. Context section labels retain the original receipt's section state; new section overrides and their corroboration are retained in the full JSON. This explicitly distinguishes native recognition observations from synthetic candidate credit.

The 83-line audit covers unrecognized headings, inherited sections, unknown colon headings, custom list inference, unheaded prose, employer capability lists, role descriptions, duty/qualification introducers, mixed role/recruiting paragraphs and administrative value aliases. Unsupported title/heading and nested-list variants remain conservative. Every recovered source occurrence is traced to original raw JD text; no résumé facts or ownership are inferred.

## Prioritized cases and allocation

**Job 35.** `Skillset:` is structural. The original analytical/problem-solving, attention-to-detail, communication and teamwork statements are candidate qualifications, not administrative values. Four rows are recovered with their original parent allocation and importance. `This is a 2-Year Contract` and the accompanying shortlisting notification are administrative. The introductory role-purpose sentence is harmless context under the bounded rule, rather than a candidate technical claim.

**Job 48.** `Other responsibilities include:` explicitly introduces the three duties. Support analysis, dashboard training/consultancy and knowledge transfer in data analytics/modelling are recovered; the introducer does not consume an allocation. The fixture's original spelling is **“leaner profile data”** and its original punctuation is retained; the policy does not silently rewrite it to the wording in the request.

**Job 359.** `Period`, `Permanent`, `Location`, the Jurong East/shuttle value and the weekday schedule remain non-scoring. Their five invalid allocations are not restored. The three initial unheaded duplicate posting values are linked to the independently identified later field/value occurrences. Resolving those metadata receipts cannot lift the existing coordinated ownership review; whole-JD availability still follows that quarantine.

**Job 45.** The administrative contract period remains excluded. Resetting that boundary also removes the generic “Those with relevant skillsets and interests may apply” invitation from an inherited requirement allocation. This is the additional geometry delta beyond the requested recoveries; it states no concrete candidate capability. The diagnostic distinguishes this observation from the independent contract-period expectation. Technical qualifications and explicit location/shift eligibility next to administrative fields have dedicated positive and mixed-content controls.

Parent weights are not redistributed among surviving rows. The native canonical IDs and original parent occurrence IDs are preserved for unchanged requirements. Duplicate sources remain receipts, not duplicate allocations. The final comparison records every existing-row allocation/importance difference and every added/removed ID; the observed deltas are tabulated below.

## All 30 comparisons and withholding

Counts and allocations use version order **v1.17 / v1.20 / v1.22 / v1.23**. `A` = available (numeric zero against empty evidence); `U` = unavailable/null. Metadata counts are source occurrences, including headings and repeated values, not removed scoring-row counts.

| Job | Requirement counts (17/20/22/23) | Parent allocation (17/20/22/23) | Retained v22 IDs | Recovered IDs | Metadata occurrences v23 | Unresolved v23 | Availability (17/20/22/23) |
|---|---|---|---:|---:|---:|---:|---|
| 15 | 28 / 28 / 28 / 28 | 25.999999 / 25.999999 / 25.999999 / 25.999999 | 28 | 0 | 0 | 0 | A / A / A / A |
| 16 | 35 / 34 / 34 / 34 | 25.999999 / 25.999999 / 25.999999 / 25.999999 | 34 | 0 | 0 | 0 | A / U / U / U |
| 31 | 25 / 25 / 25 / 25 | 19.999999 / 19.999999 / 19.999999 / 19.999999 | 25 | 0 | 0 | 0 | A / A / A / A |
| 35 | 22 / 22 / 16 / 20 | 18 / 18 / 12 / 16 | 16 | 4 | 1 | 0 | A / A / U / A |
| 44 | 20 / 20 / 20 / 20 | 14.999999 / 14.999999 / 14.999999 / 14.999999 | 20 | 0 | 0 | 0 | A / A / A / A |
| 45 | 24 / 24 / 23 / 22 | 21.999999 / 21.999999 / 20.999999 / 19.999999 | 22 | 0 | 2 | 0 | A / A / U / A |
| 48 | 17 / 17 / 13 / 16 | 14 / 14 / 10 / 13 | 13 | 3 | 0 | 0 | A / A / U / A |
| 50 | 12 / 12 / 12 / 12 | 9 / 9 / 9 / 9 | 12 | 0 | 0 | 0 | A / A / U / A |
| 72 | 24 / 24 / 24 / 24 | 21 / 21 / 21 / 21 | 24 | 0 | 0 | 8 | A / A / U / U |
| 81 | 22 / 22 / 22 / 22 | 19 / 19 / 19 / 19 | 22 | 0 | 1 | 1 | A / A / U / U |
| 141 | 10 / 10 / 10 / 10 | 9 / 9 / 9 / 9 | 10 | 0 | 0 | 0 | A / A / A / A |
| 144 | 21 / 21 / 21 / 21 | 16.999998 / 16.999998 / 16.999998 / 16.999998 | 21 | 0 | 0 | 0 | A / A / A / A |
| 146 | 43 / 43 / 43 / 43 | 28.999999 / 28.999999 / 28.999999 / 28.999999 | 43 | 0 | 0 | 1 | A / A / U / U |
| 158 | 28 / 28 / 28 / 28 | 25.999999 / 25.999999 / 25.999999 / 25.999999 | 28 | 0 | 0 | 0 | A / A / A / A |
| 163 | 49 / 49 / 49 / 49 | 30.999998 / 30.999998 / 30.999998 / 30.999998 | 49 | 0 | 0 | 2 | A / A / U / U |
| 173 | 23 / 23 / 23 / 23 | 22 / 22 / 22 / 22 | 23 | 0 | 0 | 0 | A / A / A / A |
| 187 | 31 / 31 / 31 / 31 | 29 / 29 / 29 / 29 | 31 | 0 | 0 | 0 | A / A / A / A |
| 240 | 31 / 31 / 31 / 31 | 30 / 30 / 30 / 30 | 31 | 0 | 0 | 16 | A / A / U / U |
| 319 | 15 / 15 / 15 / 15 | 12.999999 / 12.999999 / 12.999999 / 12.999999 | 15 | 0 | 0 | 12 | A / A / U / U |
| 359 | 30 / 29 / 24 / 24 | 29 / 29 / 24 / 24 | 24 | 0 | 12 | 0 | A / U / U / U |
| 361 | 13 / 13 / 13 / 13 | 13 / 13 / 13 / 13 | 13 | 0 | 0 | 0 | A / A / U / A |
| 370 | 19 / 19 / 19 / 19 | 19 / 19 / 19 / 19 | 19 | 0 | 0 | 0 | A / A / U / A |
| 479 | 34 / 33 / 33 / 33 | 32 / 32 / 32 / 32 | 33 | 0 | 0 | 1 | A / U / U / U |
| 493 | 17 / 17 / 17 / 17 | 15 / 15 / 15 / 15 | 17 | 0 | 0 | 5 | A / A / U / U |
| 551 | 13 / 13 / 13 / 13 | 13 / 13 / 13 / 13 | 13 | 0 | 0 | 0 | A / A / U / A |
| 556 | 23 / 23 / 23 / 23 | 17.000002 / 17.000002 / 17.000002 / 17.000002 | 23 | 0 | 5 | 11 | A / A / U / U |
| 566 | 29 / 27 / 27 / 27 | 25 / 25 / 25 / 25 | 27 | 0 | 0 | 0 | A / U / U / U |
| 595 | 16 / 16 / 16 / 16 | 16 / 16 / 16 / 16 | 16 | 0 | 0 | 0 | A / A / A / A |
| 632 | 27 / 27 / 27 / 27 | 13.999999 / 13.999999 / 13.999999 / 13.999999 | 27 | 0 | 0 | 0 | A / A / A / A |
| 644 | 15 / 15 / 15 / 15 | 15 / 15 / 15 / 15 | 15 | 0 | 0 | 1 | A / A / U / U |

Observed totals: **716 / 711 / 695 / 701 rows**; **0 / 4 / 20 / 13 withheld packets**. v1.23 resolves 25 of the original 83 ambiguous lines: four qualifications, three duties, eight administrative occurrences and ten context/title occurrences. Fifty-eight remain unresolved across ten packets. No existing retained row changes allocation or importance; seven independently justified rows are recovered and one generic invitation is removed.

Whole-JD availability is restored for **35, 45, 48, 50, 361, 370, 551**. Classification ambiguity remains for **72, 81, 146, 163, 240, 319, 479, 493, 556, 644**. The original coordinated withholding on **16, 359, 479, 566** persists, so 479 appears in both categories. Resolving the title/metadata ambiguity in 16/359 does not override their ownership review.

The final machine-readable comparison is retained locally and ignored at `reports/jd_ambiguity_runtime/offline-release-99379824c0844435a349a35f1060e9bd/coordinated-checks-fe0ccee151594fd8a6ad60ce07fe27ce/jd_metadata_v123_diagnostics.json`. It includes every raw JD, classification/source receipt, native and revised row ID/importance/allocation, parent provenance, score availability, full fingerprints and exact row deltas. The report and audit appendix are review artifacts; exports remain observations, not scoring oracles.

Every version receives the **same empty synthetic candidate evidence** and frozen raw JD, with frozen/injected empty structured extraction. There are no live candidate or historical candidate score claims. A numeric zero in this diagnostic means governed scoring against that deliberately empty evidence; unavailable remains null.

The v1.20 comparison holds coordinated decomposition constant against v1.22/v1.23. Published v1.17's separate row geometry reflects its earlier decomposition, not an effect of the ambiguity refinement. “Retained” counts describe previously admitted rows; they do not assert independent semantic approval of every corpus requirement. Independent genuine recoveries are the four Job 35 qualifications and three Job 48 duties.

<details>
<summary>Full per-job fingerprints (version identities are defined below)</summary>

| Job | v1.17 | v1.20 | v1.22 | v1.23 |
|---|---|---|---|---|
| 15 | `8487654def6fe4182a1de38fc2daeaee0da5ea6abd0e054e095fdccf0acd2703` | `12251a4086c02ef52e891503b3931a19808a3f58aca3a1718584e49bc3287957` | `65bb3029777ef9958d5b4e32b26d3550a6a998534e5d0c5b23244e8b87f1d0f9` | `1b0eff20f9152264bc4a90d268bd675d21f38c314b25a5c412a3642c28965bcb` |
| 16 | `9808af2267d4e79d96230a82c4eeebc355f107deae53f4956f08dba151084649` | `7f7381e89d965990f278ca7cb585c12e5e4a62f1f8f4a2b9f829798406e484a0` | `f0c5c7fcdaf8a7df26653458693a3d0511cd665eb69816c10ae891da6e1e9493` | `41ddd145745ae3bbe7a2d5656cd0cf97f9ab00c6d21076151d3e8559897efd20` |
| 31 | `33d6345f9eee4beddda990bfa4d82f5681473a9c67e56ea63f62a0beb6f5440f` | `cb039a7dc6ce2a9f23af083f4be0a663a02e90f6cecb22ad1fe3fb35e29d1ded` | `4ef3179f7def05af6f616715e500324c23782ff96599661c4751a999927738c5` | `c76ea524bc3cd56c60eb4b91c5d46cc6e1f3d811f603b8f43922c318a1d2212c` |
| 35 | `c577a0d3c44b68c058577bb1d90646cdbc40a605060f89096547a1534909c873` | `df8d1883f66054d882390a82f18f5974b752ed049d3afa9c2102b7a94801e5d2` | `f86a5806b5a0cd36211332685dd7ad135e4782836737b55dd6345957d9762cf9` | `ffb5aba412ad4789205899192072590a181c22c5faa70e01bcd5670796caeb1c` |
| 44 | `7faa0af439f7231c56c35f4af9f71134d387c70e5e616d5f9616f1a35a08722e` | `b1576304544455613b89b9a7ad48b802403093348db48fa8fe104d8e8f4bd613` | `61ecf60fee91d422e7f88921abff10563596e746f493555731dd9810e3bde32f` | `345d47c355ab33c85945d8c1df9840c6875d4886484ff0216ac0cd771ac0a341` |
| 45 | `305768cfe01a736c402dacc2d61345a97beb6933efaff794d298a611f019d2a2` | `8518cffbc5cfe38712117834e66f921cb8baefcf340d3cfe97992352189c9e8d` | `a99e91c98b8a93343bba7e215095c7069b808f1f88d4288cd1669442492f07b1` | `a85d92d47c3ee8085d188947cc76242bb142de9907c9ac38995e2605fd91fa49` |
| 48 | `679b3c9b2cdfce7d3da4a99b4dc276f3f0c8454206ef0d3631191d8f2fec1588` | `9493c5564e572efc277ee914afc5ff1c00291628609f189b7bec6a673ae3a0ed` | `898d33ce03351daa2423b277914c033a5d770b6609c5218476cd9ba03fc28f22` | `28eae54766ff9c470c0de27c4f86216b5447c63fd578d39ff499f5e640aa532f` |
| 50 | `8b6e59a2ac9d7dc7db1047dc4572a3126aee15cd5e28bb9e398f1983713e8ebc` | `5e1ef4de2da7253d12886760674f6374e4cea37be4f1ee77a8c38e9577f6255f` | `a9b8c2d0f00d98be19fff4abb64178bfe8d7f79a668fb3723e88786023dd5742` | `88a883081399b2f18cba6aed011ca42974ff8c26da6e6fba76426937fc64024a` |
| 72 | `d10993b2bb3f7e3dd7045fbce6686b69e4ad54bd9d2125965adae0bb1397432b` | `51742682eb43d092c6efab888d3c75441e3f33744683c4323552d81e5e616041` | `aa1c8bdae666e483f821a93c3321f66ec1a5a094700fee7ab4835f1f2d11facd` | `9c7ae80b2655d0d9c5bbb17c181687eea356f230229f1b2809f28407be85cb1f` |
| 81 | `789043ac6e13391439ed08710f2f2d2d3a2523b0177cc2ee75aa89a157ae2911` | `9aa3511ffe96b6d968ec958a71cdb881f83c3fe52355416b36897df8426fa46e` | `4264d59131ce79c740a010cb19eb0356e6e2fac036876cc07cee37a96d412d6b` | `4e1102d1617b1e7283bcc64f1e35c70c26e8e6a751e137498d86f5bbe50b7af1` |
| 141 | `75ca31d4bb1f7257f02e7d54183b0d6e3badd1840cb2ded0eeec8e5779a9195b` | `afbc506eb7136dd3228539c00323462f70b2a411fd41335d86aedf6e35d990d3` | `c12dc8906ce276f0dd5ca55ec99597ab4d66d65016e93333ec7466b06180d885` | `b5cee6277f483d01039ac0f37354d911b3c63b9ea74dd76366e3552e3c9474b0` |
| 144 | `a8923c9359a0336aec54f2324ec9d60a7b3734d19b6f5f373ca8e0e21f6ba285` | `57e41a5182e2ebd32379e18149851284e3ddf4472f59fa7a638b6049d73704a0` | `35dc932d95246bb8aac36fefc21bb4dccfacb932d92260a92495e44dc0b03843` | `1c0bd5e45ff110d2127d681e1bf8fa5e2866a0045ee9c08586841e06a0aaf515` |
| 146 | `308341930687c28b18100a62220647367b3844cf5ef1a8328cf6fd1aa9407691` | `57de0e5de2d9f9658476339f412cbc4c07334f1214798f200a0b503fe4af6aa5` | `f8ce0e1c2573a05f664ec91e92d308e42999a3b02953d008193c6e13964c1dfc` | `ebcf5a070715b6513f4f14cf96dc0c52108a42498abc03cf83307aa4d0a50a06` |
| 158 | `0df280b6ff74cf614ab33a97519271a7b9091be56d2596e78d21154dd9db38ef` | `622d9f07e4e6bac80b4f7bb7f14634c08624f1f3c7c762b836be2ffc9d8faf88` | `19ed8190eeb111be31d5ca06f49b662d610e4d112c6dc3bff0edec0d0aa34b28` | `f5c2db58f02a650a283207a9390eafe19dfd97f3d799d45d40de2ab2d1407913` |
| 163 | `22b52d44c2659fe87d10b682becbdf944a8887d7b4137ed169977f5b86098b18` | `305abc605366156e6bb4f1067fb1be3c4a3750f0ba94a5d310c561221bd48829` | `f2edf035be680791a64afcecbad9890926b1105954644116a4a0db393593cd93` | `258611806c1dba67f423ac1b6372f0221e048d790db125a103db2fe71bd9b921` |
| 173 | `c663cf3375f7354dcb20e20089f23f81498ee9f6fe11eecacef0c3c076d1a3ae` | `ccc5adce9a19467e9ff0be39c39a4b92dcf7193d32c124c516ee2907d82d7e00` | `2b44186ce225d90ad07b1d3e137fe85d253d2902c235a474e14a24268581608b` | `7f73a314d7d1431eaca3175f68aefac9407c9d769f8f7b890f30cde87eed873d` |
| 187 | `625efce08e46809d95a0a3aea490b7803567c364afadd2d23390c264e8d880ca` | `9f7b5fa422aea5908850906032ce50bfcb2aa5751dc0ccfa7e04c6755256fe0a` | `81e772de6cdd8515f88390f99ed9bb8cecb4d92f31df395bb36367962b114818` | `1283241e2056abf208ef9039f105d4a723422af139bd69f24beb2317cde6d426` |
| 240 | `0f63fbb8eb1b516fc91937b38e9e88b82b6c70b21731af2b462714a06ceb69c8` | `36c326dfe0f583ac5b96a5531c667e77077536d4aeb30993c212b8b8ddfd9a74` | `d3288f91bd5071bd4d4b64df748633bdedff8268eedaf5777bac43fc3721f221` | `fb008295a748f9c0fb1e0ef86271fa90c40c25e951d27f61403824a67f6ebac8` |
| 319 | `16405c3110ec0b2c283d78f9cf25ac1f5ec1a060ad72110867fbe41fa39fa6e3` | `68c46fe29e412b96a3db123fa3f204c84ef33f253b4d1df9900e3399f1166c66` | `d304f3aa1d45baa213e2e80070fed43d0f188487c7596cd6ac7c43b018db0791` | `0a1e79180fdc214c09238745cd1bd2168af491b4d325d9ae3d85bcebd9cb4ec0` |
| 359 | `840e3c6febf51df44bbcc0603513baa9e47e47b14a7d7202607fba44be85af84` | `34e3187ee45a696f3fdb1b38abd26a295768ead7ec515f35afc9e1fc80270a15` | `d4c48ec03896af04b5a2a5be4cb5a622137a07d232f9c0a1d80084b1a9c48316` | `a6873cf9f6c5026e18991d2d27e5c5cf0e32f4e02686ea67f4cd0885cdd96ac1` |
| 361 | `39c4e07838cbe4e099ca386b80ddb20820091fb7a7bc211ab00fe690d0433716` | `910b9d6f695f68c12eae6a96023d2ecd7a621ae85a885d1bc457b37dd8579cbd` | `77ea82a29062bb618635b94e1ab1d7b21793055d3d71b1ce46f8df57cf849a35` | `849ebcb3afb7fae0edd79066ea377becfafd14ae78fce27861265965a4625dea` |
| 370 | `24d82d80920b36061d2960196f91e8aaa2753d9da07e323c0e49649c113a51df` | `d3a8e751b86ad3a69f347d3cab571a6a35bc05c0a2414f290758b342093ecca4` | `21b2551ac965f0129fec8642fa19a1a6904fe6ba3aaad15ada1e22ef91ab4648` | `b47ca2af5f24fd7554b84536cbd2c5d2bc877265737941d0b7aeb4a0ea5a8a69` |
| 479 | `1fe3dcc6d6974c1093a4dd1302ecd035a9f32b79088cab2be19179a1da7c0bf9` | `e84f24257686008423f269b49272a01aa4dbc97a221ce46a10ef45c7044451d7` | `16cc33d2b107fd3ddfde8b827f4834aded4eba9db5332ba44ddc922adc5c2f3b` | `4c91f92f8d589046a2a80f5295709bd6923f7e664e3e15fe5f3e04128cd02958` |
| 493 | `18436207f8dfc1f19c314a8a6eb2036d01a01f435cf060c8046946d016396580` | `f047aa229f1cf49c35c35f4d661eb5f0229d90c65d98395f9aa184f518804527` | `cc2c885e18cff6ae1673d68895c4192bfe04c4dc16e7bf01291e0b8e4aea40d3` | `fb274b2305f1b26379403d229066fe45998c3e7f7d71d29fe7ebae8eb7369da1` |
| 551 | `5e56b77259bdd2ee617d909bbdfcbacc9e0198e1aa08905b4f2eb2c8d05909bc` | `13b7612ab6da8815cac4cbf55e1919df5cce70ec87c956d29fd55a813a29f397` | `1f3e1229ff4e5b01eef72afa537a37a6c243e595bf8eee9d5c08d8f1bba5f545` | `06b720d1047d19db2d21b37b93d5c206b422e0a8685d50e83fae639787b2d5b0` |
| 556 | `e477d8d77bd3572ccfa565b6a7982914a832b70a057a95dd28b6bc82f0db3409` | `ea3b56dc9e799917a4666f5ebf08f4d491d499c689dc1e957be04d3a00e203a9` | `fb32d96706a4319d57d0adee0da2cc6fde5c0dca673a5067bfa39e6f7a129b03` | `e538b85b7e947f4721fa7f53b228cac1cd93c9869bf2ff5c3e70fbcc9b39053e` |
| 566 | `8d49778a263f544231046d3d90c0ad1ca7f4c193a6bb4b4553cf5e7eefbf68b7` | `fa33446aebdcef4fa7fc6d73f10ae4909edbab96290ea80729a6f09f7defd96b` | `f1b499503503b954027225c6085aa5d362744248d6614227c524e97164b4123f` | `892f17f2f32ff3135a8cb852699982472412212970c46e7ac2af5745e5d0a8b8` |
| 595 | `f5e9ffbcef4ff45ae4aa7aa109b25054b9422104eda1476e342d0a8de4dc0407` | `7ac21e28a4cd3f74cce875608c2b72921b55989673c15a1909f5b134785fcdaf` | `98526cdcecbe6f2f5dbba2e0fa8125cd41eab39478a04f27ff2e1c097f0a4daa` | `d43b808dba22634374f2e1ba8874dd3be47e58e0024f42fec6d1d21fca6304b2` |
| 632 | `bf0460a7076b720bca34c70c92f235760eca131355941315b462a3ee020d32de` | `73163fdbac50472469ca85e70d086a1b12625a718ac72d52d5a326a3517fb3e6` | `8e1fb26d9390272f947cfaead67df7065ef84600f4d80ae6bf119efff0201eb0` | `d3933007a0307fd918555689ad48d933fbf15629c2a51ca46f7c242179128270` |
| 644 | `4c9fb131adf19e825c667fd0e3e8b182c3734a0b26fe72eb34edaf496690c209` | `48a92714c011d6be2b85f760de83f4b350164413493c42134fa85bb108a53ca4` | `736a94f117fd860808ee6fa3c68315398b8762729cedca275cc755476be5b9a3` | `b36039914e84d500dade0d8fd112f700a6e5cb7eedee86d32953f4682d47e265` |

</details>

## Version isolation, cache and rejection

| Route | Identity / state |
|---|---|
| Published default | `stable-evidence-v1.17-phase6d21`, unchanged |
| Original coordinated gate | `stable-evidence-v1.20-phase6d24`, unchanged |
| Source-aware library gate | `stable-evidence-v1.21-phase6d25`, unchanged |
| Earlier metadata experiment | `stable-evidence-v1.22-phase6d26` / `jd-administrative-admission-v1`, unchanged and reproducible |
| New explicit experiment | `stable-evidence-v1.23-phase6d27` |
| New classification policy | `jd-administrative-boundary-refinement-v2` |
| New preview namespace | `jd-metadata-comparison-v2` |

Use `analysis_stability.jd_metadata_v123.build_metadata_preview(developer_enabled=True, ...)` with explicit original raw JD and synthetic/injected inputs. Omission of the developer flag raises. No environment, default builder, model extractor, application route or UI dispatch selects v1.23 automatically. The existing v1.21 preview page is not switched.

The fingerprint binds the original raw/profile authority, classification receipts, version/namespace and full underlying pipeline/evidence/projection fingerprint. Different raw inputs or policies cannot reuse v1.22 identities/caches. Repeated identical requests are deterministic. The request-local context resets even on an exception.

The v1.22 module remains byte-identical to the checkpoint. Independent execution with the checkpoint native parser reproduces v1.22 outputs on Jobs 35, 48 and 359. A new optional native structural-receipt hook is a no-op for published and earlier experimental records. Scoring constants, taxonomy, registry, evidence ranking, P3/R1/API V1.1 and ownership/conflict algorithms are not changed.

Bare v1.23 identity is added to the common preview guard. The existing publication, ranking, summary, normal application refresh, public Job Match writer and low-level analysis insertion protections reject it before database I/O, including when preview flags are stripped. No gated persistence or historical cache migration is enabled.

## Regression results and commands

- **157/157 PASS in one clean combined run**, 328.764 seconds, zero failures/errors: `reports/jd_ambiguity_runtime/combined157_release.log`. All **854** frozen Python/JSON source files are hash-verified unchanged throughout this run. Earlier exploratory runs were deliberately stopped before boundary corrections; they are not counted as final verification.
- **15/15 new v1.23 tests PASS**, 14.577 seconds: `reports/jd_ambiguity_runtime/policy_release.log`. Includes the independent Job 35/48 expectations, Job 45/359 exclusions, notification and mixed-contract controls, bare technical content after administrative fields (including a blank separator), explicit eligibility, technical-word boundaries, unknown headings, preferred/duplicate/wrapped/nested lists, source spans, exception reset, v1.22 checkpoint isolation, cache determinism and pre-I/O rejection.
- **1/1 diagnostic export PASS**, 87.519 seconds: `reports/jd_ambiguity_runtime/diagnostic_release.log`. Every one of the original 83 ambiguous lines is accounted for, with 91 total audited occurrences including the boundary controls; all 30 version comparisons use identical empty evidence.
- The original combined run covers all 60 coordinated cases, all 38 realistic-profile expectations, all 30 published-OFF comparisons, API V1.1, P3/R1/native NONE, source projection, E23/E04/E05/B05/E24/C03 protections, stale/cache/currentness, retained UI interactions and gated persistence rejection. No historical expectation or existing test assertion was changed.
- Syntax and Git whitespace checks pass, including new files and the empty staged diff. The final protection ledger is `reports/jd_ambiguity_runtime/protection.json`; only the two explicitly described existing source files differ from entry. The v1.22 module, old fixtures/oracles, prior reports, taxonomy, registry and containment scripts remain byte-identical. Branch/HEAD and the empty index are verified.

Supported interpreter used: `venv/evidence-completeness-runtime/environment/Scripts/python.exe -B` (Python 3.13). Commands:

```powershell
python -B scripts/run_offline_release_checks.py --scratch-root reports/jd_ambiguity_runtime tests.test_jd_metadata_v123

python -B scripts/run_offline_release_checks.py --scratch-root reports/jd_ambiguity_runtime scripts.preview_jd_metadata_v123

python -B scripts/run_offline_release_checks.py --scratch-root reports/jd_ambiguity_runtime tests.test_coordinated_batch_dashboard tests.test_coordinated_action_implementation tests.test_coordinated_r1_disposition tests.test_coordinated_conflicts tests.test_coordinated_conflict_acceptance tests.test_coordinated_realistic_evidence_audit tests.test_api_evidence_completeness tests.test_coordinated_library_sources tests.test_coordinated_job_match_preview tests.test_coordinated_job_match_preview_ui tests.test_jd_atomic_requirement_decomposition tests.test_jd_structure_inference tests.test_jd_structure_inference_bullet_boundary tests.test_jd_structure_inference_regression_guard tests.test_jd_structure_fingerprint_compat tests.test_jd_metadata_admission

git diff --check
git diff --cached --check
```

The existing offline disposable containment is unchanged. No live model/network/database/candidate operation is permitted. The known résumé-output full-CI write issue remains outside this task; the full project runner is not used as a substitute for the requested combined focused suite and its guard is not weakened.

## Changed files and remaining decision

| File | Change |
|---|---|
| `analysis_stability/jd_metadata_v123.py` | New isolated bounded classifier, explicit builder, withholding/identity and source receipts. |
| `analysis_stability/stable_evidence_scoring.py` | Eight-line optional structural-receipt hook; absent for earlier routes. |
| `analysis_stability/coordinated_runtime.py` | Reject bare v1.23 preview identity. |
| `tests/test_jd_metadata_v123.py` | Independent historical, synthetic boundary, source/ownership, isolation, cache and rejection tests. |
| `tests/fixtures/jd_metadata_v123_expectations.json` | Independent focused classification expectations with original source text. |
| `tests/fixtures/jd_metadata_v123_span_review.json` | Independent assessment of all 83 original ambiguous lines. |
| `scripts/preview_jd_metadata_v123.py` | Deterministic all-version/30-JD comparison and 91-occurrence audit export; observations are not oracles. |
| `jd_metadata_v123_span_audit.md` | Full reviewable source audit appendix. |
| `jd_metadata_ambiguity_v123_report.md` | This report and release decisions. |

| Decision | Result | Basis |
|---|---|---|
| Bounded parser refinement correct | **PASS within the specified scope** | Four Job 35 qualifications and three Job 48 duties recovered; headings/contract/location/schedule remain non-scoring; no retained allocation or importance changes; negative and source/conflict controls pass. This is not a claim of universal JD understanding. |
| Experimental preview ready for developer review | **YES** | Explicit v1.23 entry, independent expectations, all-version diagnostics, null withholding, guarded publication and clean regression run. Existing UI/default routes stay on their previous versions. |
| General production activation safe | **NO-GO** | 58 content classifications across ten packets remain unresolved; supported human judgments are not automatically implemented rules. Persistence/currentness/UI activation has not been approved or integrated, and the separate full-CI artifact issue remains outside this task. |

Remaining cases are explicit rather than hidden: Job 72's employer capability list; 81's unheaded role duties; 146's organisation description containing third-party skill language; 163's mission/project/recruiting prose; 240/319's custom duty introducers and mixed employer context; 479's recruiting qualification sentence; 493's organisation headings/narrative; 556's job introduction and gerund duty list; and 644's mixed role/recruiting paragraph. Some are plainly genuine duties or harmless context to the analyst, but exceed this finite automatic rule set. They stay reviewable, never fabricated absence or complete candidate credit.

The smallest next action is human review of the new expectation fixtures, the bounded automatic rules and the remaining source receipts. Keep those unsupported packets withheld; do not broaden the detector merely to increase numeric availability. Any optional developer UI policy selection or later production rollout is a separate approved integration step.

Do not expand this into general language recovery to obtain 30 numeric outcomes. Review the demonstrated bounded rules and remaining original source receipts. Unsupported responsibility headings, mixed unheaded role paragraphs and generic capability/organisation narratives need further independently reviewed policy if broader recovery is desired. Any production activation, UI dispatch or persistence/currentness migration requires separate approval. No staging, commit, push, merge or production data changes were performed. Stop for review.
