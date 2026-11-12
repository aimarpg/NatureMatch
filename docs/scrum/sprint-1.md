# Sprint 1 tasks and starting order

Sprint 1 runs from **3 to 17 November 2026**. Its goal is to show that the selected hardware works and produces a trustworthy local status. These issues describe work to complete; creating or renaming them does not demonstrate working hardware.

Use the [GitHub Projects board](https://github.com/users/aimarpg/projects/1) to track progress. The [initial project plan](../../Documents/Project%20Initial%20Plan.pdf) defines three dated sprints and narrows the [proposal](../../Documents/IoTChallenge.pdf), which originally described five stages. The board follows the dated plan. Its Sprint 1 sensors are infrared, temperature/humidity, noise and light; UV, gas sensing and NFC remain optional.

## Set up and plan the project

| Issue | Task | Module |
| --- | --- | --- |
| [#47](https://github.com/aimarpg/NatureMatch/issues/47) | Set up the project structure | operations |
| [#7](https://github.com/aimarpg/NatureMatch/issues/7) | Set up GitHub Projects and team access | coordination |
| [#48](https://github.com/aimarpg/NatureMatch/issues/48) | Create and organise the project issues | coordination |
| [#49](https://github.com/aimarpg/NatureMatch/issues/49) | Plan the project development | coordination |
| [#1](https://github.com/aimarpg/NatureMatch/issues/1) | Agree how the team will work | coordination |

The repository already contains source folders, dependency configuration, a Makefile and CI configuration, alongside unfinished placeholders. Issue #47 checks and documents that scaffold rather than assuming it is ready to run. The earlier description of a documentation-only repository conflicts with these files; their presence does not establish working sensors or a validated application.

## Check the hardware and test each selected module

A sensor test here means a small Python script on the Raspberry Pi that reads one physical module, demonstrates its response and records what happens when readings fail. It does not require the shared JSON format or the complete application.

| Issue | Task | Before starting |
| --- | --- | --- |
| [#4](https://github.com/aimarpg/NatureMatch/issues/4) | Check the available hardware and wiring | Can start immediately |
| [#2](https://github.com/aimarpg/NatureMatch/issues/2) | Test the distance sensors | #4 |
| [#5](https://github.com/aimarpg/NatureMatch/issues/5) | Test the temperature and humidity sensor | #4 |
| [#6](https://github.com/aimarpg/NatureMatch/issues/6) | Test the noise sensor | #4 |
| [#38](https://github.com/aimarpg/NatureMatch/issues/38) | Test the light sensor | #4 |
| [#8](https://github.com/aimarpg/NatureMatch/issues/8) | Test the LED bar | #4 |

All six issues belong to **station**. The LED is an actuator rather than a sensor, but its physical test belongs with the station hardware. Confirm the actual model, voltage and interface before wiring. Record physical test results separately from simulations. Noise testing measures the module's response without recording or transmitting audio; reliable decibel claims require calibration.

Issue #2 currently names distance sensors, while its description and the proposal refer to infrared beams. Confirm the actual modules and crossing approach in #4; this backlog organisation does not resolve that hardware discrepancy.

## User stories and issue references

User stories track outcomes and acceptance criteria. Feature-specific implementation and validation tasks are sub-issues. Setup, initial hardware tests and shared infrastructure remain independent, with reciprocal references in each issue's User story references section. Independent prerequisite links describe what the final outcome needs; each task's Dependencies section determines when that task can start.

| Story | Feature-specific sub-issues | Independent prerequisites |
| --- | --- | --- |
| [#50 See how busy the space is](https://github.com/aimarpg/NatureMatch/issues/50) | #3, #40 | #2, #39, #9 |
| [#51 Check the current environmental conditions](https://github.com/aimarpg/NatureMatch/issues/51) | Delivered through shared tasks; no duplicate children | #5, #6, #38, #39, #9 |
| [#52 Understand conditions through the LED bar](https://github.com/aimarpg/NatureMatch/issues/52) | #41 | #8 and one verified source from #3, #5, #6 or #38 |
| [#53 Check whether the place suits my activity](https://github.com/aimarpg/NatureMatch/issues/53) | #16, #17 | #39, #14, #18 |
| [#54 Review past conditions](https://github.com/aimarpg/NatureMatch/issues/54) | #15, #19 | #39, #13, #14 |

Stories #50–#52 target the Sprint 1 local demonstration; #53–#54 target Sprint 2. Their later integration and regression references identify subsequent work, including Sprint 3 checks, without holding the initial outcomes open for every future enhancement. Setup, coordination, release preparation and optional features retain their existing independent issues.

Story estimates remain blank. All effort stays on the existing technical tasks, so adding stories does not add implementation hours. A story is complete only when its acceptance criteria have linked evidence, including work delivered by independent shared tasks; child completion alone is insufficient.

## Turn the readings into a local demonstration

| Issue | Task | Before starting |
| --- | --- | --- |
| [#3](https://github.com/aimarpg/NatureMatch/issues/3) | Count people entering and leaving | #2; counting logic does not wait for environmental sensor tests |
| [#39](https://github.com/aimarpg/NatureMatch/issues/39) | Define the sensor data format (JSON) | Draft while tests run; confirm with outputs from #2, #5, #6 and #38 |
| [#40](https://github.com/aimarpg/NatureMatch/issues/40) | Compare the people counter with manual counts | #3 |
| [#41](https://github.com/aimarpg/NatureMatch/issues/41) | Make the LED respond to station data | #8 and one verified source from #3, #5, #6 or #38 |
| [#9](https://github.com/aimarpg/NatureMatch/issues/9) | Show live station readings on a local web page | #39, #40 and #41 |

**Station** owns wiring, sensor drivers, physical tests, entry/exit processing and this first local demonstration. **Data-model** owns the shared record fields, examples and software checks: station identity, unique record ID, measurement name, observation time, value, unit where applicable and quality status. A missing reading stays missing rather than becoming zero. Sensor tests produce sample readings; #39 defines how the rest of the system will understand them. The same person can own work in both modules without changing these boundaries.

The fuller API, InfluxDB storage, Grafana and visitor interface follow in Sprint 2. The local status page in #9 belongs to station integration; it does not imply that the full service is complete. Plain HTTP is limited to a controlled isolated test network.

Start occupancy from a known count. Compare entries and exits against manual observations, including pauses, reversals, incomplete crossings and different speeds. One monitored entrance establishes whole-area occupancy only when every way into the test area is controlled. Keep occupancy, noise and any optional NFC registrations separate.

## Review the sprint

Use [#25](https://github.com/aimarpg/NatureMatch/issues/25) for the **17 November product review** and [#43](https://github.com/aimarpg/NatureMatch/issues/43) for the **team retrospective** afterwards. The review inspects the working result and feedback; the retrospective agrees how to improve the team's work.

The planning envelopes remain **14 implementation hours, 4 coordination hours and 3 contingency hours**, measured as total team person-hours. Repository setup is estimated at 1 implementation hour. Workflow, board setup, issue organisation, planning, review and retrospective currently total 3.25 coordination hours, leaving 0.75 hours for other coordination. These are forecasts to check against actual progress and availability, not records of time already spent. Keep tasks open until their checklists and evidence support closing them, and record actual work dates rather than backdating missed checkpoints.
