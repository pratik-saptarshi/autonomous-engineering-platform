# Brainstorming

## Decide whether to ask first

- Before you reply, ask yourself what you actually know about what they want and why.

- If everything that matters is in the request, do the task and say what you did. This skill is done.

- If something non-trivial is missing, start the conversation below instead of building.

## Send the first message

- Write one line letting them know they can skip the questions and have you just start. If they take you up on it, state any significant how-it-gets-made choice in one plain line, then do the work through the normal workflow.

- Follow with one open question that gets them describing a real moment. Ask about a concrete picture, such as the moment they find themselves wishing this existed or who will be in the room when it is used.

- Send only those two things, in that order.

## Run the conversation

- End each message with one question, a single sentence with no list of example answers hanging off it.

- Use plain language pitched just above where they are. Match their vocabulary and never use process jargon.

- Get them describing before you offer options. Open questions come first because their own words carry intent your options cannot. Offer a short menu only when they are stuck. When they say just guess, propose something concrete.

- Settle how it gets made early. Find out which choices about medium, tools, and materials they want to make, which they hand to you, and what they already have. State your defaults in plain words. Build on what already exists. Mark any choice you make as your call, never as something they agreed to.

- Treat this as territory to cover, never as a script to read out. Cover what kind of thing this is and what makes it special, why now and what success looks like, goals plus non-goals plus anti-goals, prior art they loved or hated, the current state and what they have tried, and the details they care about.

- Anchor questions in specifics. Ask them to walk you through the last time, or which of two things matters more, or what would make them wince if you got it wrong. A guess they can correct often beats a question.

- Offer recon once you have some grounding and looking would help. Say what you would look at, such as their files, their data, or the web, and let them decide whether you go.

- Think wide privately. Come up with several ideas before you propose anything and drop the weak ones, including any that fight what they told you about why. Show the comparison only when it helps them decide.

- Offer to show rather than tell whenever seeing would help more than reading. For screens, layouts, flows, side-by-side options, or diagrams, offer to build a quick visual with the artifact tools. Make the offer its own message and wait for a yes before building.

- Offer a throwaway spike when building something quick would teach you both what they want or whether an approach works. Spikes get no tests, are not bulletproof, and skip planning. Bring what the spike taught back into the conversation.

## Play it back

- As soon as you understand one part well enough to describe it, describe that part back in about 200 to 300 words, then return to questions about the next part. Alternate playback and questions through the whole conversation.

- Mark anything you are guessing as your guess. Only what they said goes in as theirs. End each chunk by asking what is wrong or missing.

## Size the work

- Once you understand what they want, name the size in plain words and let them override it. A quick clear task gets done directly. A small change gets a short description in chat and then built. A project gets a written design document and then a full plan.

- If the work grows mid-task, stop, say so, and step up a size.

- If this is really several independent projects, say so, agree on an order, and brainstorm them one at a time.

## Write the design

- For a project, write a plain document a talented builder could plan from without going back to them. Cover the intent and the why, goals and non-goals and anti-goals, constraints, the how-decisions they made as they made them, and what is left to the builder.

- Ask where the document should live. A good default is the relevant goal workspace under `~/workspace/goals/<goal>/files/` or a document artifact they can keep.

- Before handing it over, dispatch a fresh subagent with `subagent.spawn` to read the document as the builder and list every question it raises. Tell your human partner a reviewer will read it first and you may come back once with questions.

- Sort the builder questions into three piles. Put answers already in the conversation or project into the document. Settle minor ones yourself where a sensible builder could decide without changing what gets built, and mark them as your call. Bring only the questions that change what gets built back to your human partner in one message, most important first.

- Update the document with their answers and hand it over with a short list of the calls you made.

## Hold the hard gate

- Nothing gets built until they approve the full description. In chat for a small change, the document for a project. Building includes writing code, scaffolding, installing things, creating projects, and running implementation. Reading and exploring are fine.

- Two exceptions end the gate. They opted out of questions at the start, or they said yes to a spike, which stays labeled throwaway. Keeping spike output is a new request that comes back through this gate.

- After a project design is approved, write the implementation plan with the writing-plans skill and no other skill.

## Watch for red flags

- If you catch yourself thinking you will offer options to save them effort, stop. Options steer. Ask them to describe it first.

- If you fill in a sensible default, say it out loud. A default they never heard is one they could not reject.

- If you want to explain the process first, ask your question instead. The process shows itself.

- If they said sounds good to the idea, remember approval covers what you showed them. A description you have not written is not approved.

- If the spike works and you want to keep building on it, stop. Keeping it is a new request. Back through the gate.
