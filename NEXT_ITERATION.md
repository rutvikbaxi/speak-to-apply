# Speak-to-Apply: notes for the next iteration
(Logged 4 Nov 2026. Not implemented yet.)

## Design
- [ ] Colour theme: beige, navy blue, black, grey, cream, white. Apply it to both Speak-to-Apply and HireHub, or keep HireHub visually distinct?
- [ ] Font: Helvetica everywhere, including the resume PDF.

## Flow and questions
- [ ] Remove the "Target level" question. Derive the level from years of experience in the resume. Fit scoring should use years of experience only, not job titles (companies use designations differently).
- [ ] Merge "Company size" and "Startup or MNC". Keep company size and drop startup/MNC as a separate question and scoring factor.
- [ ] Move "Anything new since then?" so it comes immediately after the upload step (step 1), before the quick questions. New order: About you → Anything new → Quick questions → Resume → Jobs. (Check this is the intended position.)

## Resume
- [ ] Use an AI API (Rutvik will share the key) to show what changed in the resume, e.g. a highlighted diff of added or edited lines, not just the current "What we added" list.

## Applying
- [ ] "Applications will use this email": auto-fill it from the email in the resume. (This already happens when the AI extracts an email; make sure it reliably picks up the email from PDFs and LinkedIn text, and flag it if none is found.)
- [ ] Remove the LinkedIn URL field from the HireHub application form.
