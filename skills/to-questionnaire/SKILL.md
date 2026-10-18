# To Questionnaire

Turn a decision the user cannot fully answer into a **questionnaire**: a Markdown document they hand to one person to fill in async, or fill out together in a meeting. The recipient holds knowledge the user lacks; the questionnaire pulls it out of them.

## Grill the send, not the subject

- Interview the user only about the _send_, which they can always answer: who it goes to, and what they need back. The questions in the document target the gap between what the recipient knows and what the user needs.

- First, in one exchange, establish the recipient's role, expertise, and relationship to the user. This fixes the questionnaire's tone and how much context it must carry.

- Then, in one exchange, establish the specific decisions or facts the user cannot resolve alone. Stop when you have a concrete list of what the user must walk away able to do or decide.

## Write the questionnaire

- Draft questions aimed at the gap above. Order them most-important-first, since async means you may only get one pass, and group them under `##` headings by theme once there are more than a handful.

- Frame it as a discovery questionnaire: one paragraph of context orienting a recipient who was not in the user's head, then how to answer (deadline, rough effort), then the themed questions.

- Keep every question to one idea, never compound, with an answer stub directly beneath. Add a one-line _why this matters_ only where a question could be misread or invite a throwaway answer. End with a catch-all: anything we did not ask that we should know.

- Save it to `~/workspace/to-questionnaire-<slug>.md` and report the path. Done when the file exists and every item the user named is covered by a question.
