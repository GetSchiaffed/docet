---
description: Close the study session, leaving everything ready to resume
---

# Close the session

1. **Close the file you were working on** with a summary at the bottom, in a `> [!abstract]` callout, in the learner's language:
   - **What stuck**: the nodes checked in this session;
   - **What's still open**: nodes not reached, slips to retry, gaps, and any question already in the file but not answered yet (it will be asked again: the engine keeps it);
   - **Where to resume**: the next step according to `python3 bin/docet.py next`.
   A few lines per point.
2. **Align the state.** If a lesson is finished, `lesson <id> done`. If it's halfway, it stays `doing`: it will resume from there. If the session showed the course was wrong (a missing prerequisite, a lesson too big), fix it now with `plan`: this is when you know.
3. **In the terminal, one line**: where the file is, and that `/docet:next` is all it takes to resume.
