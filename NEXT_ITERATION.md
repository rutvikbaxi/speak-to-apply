# Speak-to-Apply: notes for the next iteration
(Logged 4 Nov 2026. All items implemented on 4 Nov 2026; see notes.)

## Design
- [x] Colour theme: beige, navy blue, black, grey, cream, white. Apply it to both Speak-to-Apply and HireHub, or keep HireHub visually distinct?
- [x] Font: Helvetica everywhere, including the resume PDF.

## Flow and questions
- [x] Remove the "Target level" question. Derive the level from years of experience in the resume. Fit scoring should use years of experience only, not job titles (companies use designations differently).
- [x] Merge "Company size" and "Startup or MNC". Keep company size and drop startup/MNC as a separate question and scoring factor.
- [x] Move "Anything new since then?" so it comes immediately after the upload step (step 1), before the quick questions. New order: About you → Anything new → Quick questions → Resume → Jobs. (Check this is the intended position.)

## Resume
- [x] Use an AI API (Rutvik will share the key) to show what changed in the resume, e.g. a highlighted diff of added or edited lines, not just the current "What we added" list.

## Applying
- [x] "Applications will use this email": auto-fill it from the email in the resume. (This already happens when the AI extracts an email; make sure it reliably picks up the email from PDFs and LinkedIn text, and flag it if none is found.)
- [x] Remove the LinkedIn URL field from the HireHub application form.

## Implementation notes
- "What changed" is generated with the existing Groq model (gpt-oss-120b): each change is labelled with its source (voice note, your answers, wording polish), and the resume preview highlights added and reworded lines by comparing before and after. To switch to a different AI API later, swap the model in `speak/llm.py`.
- "Anything new" now comes right after the upload step. Its follow-up questions come from a separate AI call, so the "before" version of the resume never absorbs the new information.
- When the voice note adds a new current role, any older "Present" role is ended the month before it starts, and this is listed as a change the user can edit.

# Iteration 3: notes
(Logged and implemented 4 Nov 2026.)

- [x] Font: serif (Georgia on Mac/Windows) across both apps, the confirmation email and the resume PDF.
- [x] Palette from Rutvik's reference: #10375C navy (buttons, headings, scores), #1E81B0 blue (links, hover), #B4E1FA light blue (pay tags, strong-fit factors), #F1E0C5 beige (highlights, banners), #FFFBF4 cream (page background). Black and grey are used for body text.
