JD Atomic Requirement Decomposition — Development Fixture Pack

Purpose
-------
These five real saved JD texts are DEVELOPMENT-VISIBLE fixtures for the
feat/jd-atomic-requirement-decomposition branch.

They are intentionally a small, diverse sample. They are NOT the complete
saved-JD corpus and must not be treated as exhaustive coverage.

Important testing policy
------------------------
1. These files may be inspected while designing and implementing the feature.
2. Do not hard-code company names, job titles, or literal phrases from them.
3. Add 15–20 synthetic adversarial fixtures covering grammar/formatting classes.
4. Additional real JDs are intentionally held out and will be used only after
   implementation as a generalization/acceptance test.
5. Passing these five real fixtures is necessary but NOT sufficient for Done.
6. Safety invariants (determinism, provenance, ID stability, weight conservation,
   no score inflation) are 100% pass requirements.

Files
-----

- 001_dConstruct_Backend_Engineer_jdv_2c73d7a3.txt
  Compound backend responsibilities, grouped verbs, tool/example lists, CI/CD, duration requirement, cloud/networking concepts.

- 002_dConstruct_C_UI_UX_Software_Engineer_jdv_a148af2e.txt
  Client/context prose mixed with responsibilities, C++/QML spacing noise, cross-platform UI requirements, tool alternatives.

- 003_dConstruct_Software_Engineer_jdv_4537aa97.txt
  Known long compound-paragraph regression plus extraction noise such as use cases.You, Atthe, C/C++programming, OpenGLand/or.

- 012_Garena_Associate_Configuration_QA_jdv_6a3987cd.txt
  Short clean counterexample with duration, preference wording, collaboration, domain interest, and attention-to-detail language.

- 013_Home_Team_Science_and_Technology_Agency_HTX_Lead_Engineer_Engineer_DevOps_MLOps_AI_Platform_xCloud_jdv_ec880679.txt
  Long real JD with employer prose, nested tool examples, certifications, 1-5 years, security-in-context language, and recruitment boilerplate.

Held-out policy
---------------
Do not ask for or rely on the remaining exported JDs during implementation.
They are reserved to test whether the decomposer generalizes beyond the
development corpus.
