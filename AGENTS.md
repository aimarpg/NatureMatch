# Instructions for agents working on NatureMatch

These instructions apply throughout this repository. Read any more specific `AGENTS.md` in the area you modify as well.

## Project context

NatureMatch is an IoT Challenge 2026–27 project to help people select nearby green spaces using entrance-based occupancy estimates, environmental measurements and activity-specific recommendations.

The repository is currently at the proposal stage. Implementation has not started. Do not describe planned features, example data, dashboards or security measures as implemented or validated.

Before working, read `README.md` and consult the relevant sections of `Docs/IoTChallenge.pdf`, the project proposal. `Docs/Project Initial Plan.pdf` is additional planning material. If documents disagree, surface the discrepancy rather than silently choosing an interpretation; follow the user's current direction for the task.

## Scope and implementation approach

- Prioritize the course MVP: entrance counting, environmental sensing, local processing/storage, HTTP/REST with JSON, InfluxDB/Grafana, explained recommendations and LED feedback.
- Treat NFC check-ins as optional. MQTT, LoRaWAN, managed cloud services, multi-site rollout and battery/solar power are future extensions unless explicitly included in the task.
- Use the proposed Raspberry Pi 5, Grove interfaces and Python as the initial hardware/software context. Exact sensor models, pin assignments, dependencies, web framework and service layout remain to be confirmed.
- Inspect the repository before choosing file locations or tools. There is no established source layout, package manager, build command or test command yet. Document those choices when introduced; do not invent setup instructions for nonexistent software.
- Keep changes focused on the requested task. Preserve unrelated work and original proposal PDFs. Record significant decisions and assumptions in repository documentation.

## Domain rules

- Keep infrared occupancy estimates and voluntary NFC activity registrations in separate fields and displays. Never add check-ins to occupancy or infer an individual's session end from an anonymous exit.
- Start occupancy from a known count. Full-area estimates require monitoring every entrance; a one-entrance demonstration does not establish whole-park occupancy.
- Keep occupancy and noise independent. Busy does not necessarily mean noisy.
- Include station identity, observation time, value, unit where applicable and quality status in measurement records. Distinguish missing, stale, experimental and invalid data from current valid readings; missing values must not silently become zero.
- Present gas readings as qualitative sensor responses unless the hardware and validation support more. Do not label them official AQI or pollutant concentrations. Do not label approximate UV readings an official UV Index, or uncalibrated noise readings reliable dB measurements.
- Check essential access requirements before ranking preferences. Keep unknown access or facility information explicit. Recorded table/bench presence does not establish individual availability.
- Explain recommendations and their data limitations. Label simulated measurements and demonstration scores clearly.
- Preserve local entrance processing during network outages while powered. Use record identifiers and timestamps to avoid duplicate synchronization; missed crossings require count reconciliation.

## Privacy, hardware and deployment

- Collect the minimum data needed. Do not add camera-based identification, audio recording/transmission, persistent visitor tracking or public disclosure of personal access needs.
- Keep NFC participation voluntary and sessions temporary, with check-out or expiry. Do not expose raw card identifiers in public responses or logs.
- Preserve the planned account-free visitor flow and on-device location filtering without storing user location, unless the user explicitly changes that scope.
- Keep credentials and private configuration out of version control; provide placeholder configuration examples when needed.
- Restrict plain HTTP to controlled isolated-network tests. Beyond that setting, implement HTTPS and authenticated device/administrative access; use TLS for future MQTT connections.
- Confirm module model, voltage, wiring and interface compatibility before giving hardware-specific instructions. Distinguish simulated validation from tests performed on physical hardware.
- Treat outdoor tests as supervised and sheltered. Do not claim weather resistance, battery autonomy or calibrated sensor accuracy without evidence.

## Validation and handoff

- Add and run checks appropriate to the change once executable code exists. For crossing logic, cover entries, exits, pauses, reversals and differing crossing speeds; compare physical counts against manual observations when hardware is available.
- For data and recommendation work, check timestamps/quality, missing or stale readings, access filtering before ranking, separation of occupancy and check-ins, session expiry and duplicate synchronization as relevant.
- Use clearly labeled fixtures or mocks when hardware is unavailable and report that limitation. Do not claim field validation from simulated inputs.
- For documentation-only changes, review the diff, verify local links and compare scope claims against the proposal. No application build is currently available.
- Update the README when setup, architecture, commands or implementation status changes. Keep planned, implemented and validated capabilities distinguishable.
- At handoff, summarize what changed, what was checked and any remaining assumptions or unverified hardware behavior. Report commands actually run and their results; never claim checks passed without running them.
