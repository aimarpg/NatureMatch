# Wiring and pin inventory (Grove Base Hat)

## Current hardware decision

Reported hardware (15 November 2026): Raspberry Pi 5, Grove Base Hat for Raspberry Pi,
two ultrasonic distance sensors, temperature/humidity, sound, light and an NFC reader.
LED bar and activity selector availability is unconfirmed; NFC remains optional for the MVP.

The [proposal](../../Documents/IoTChallenge.pdf) specifies two infrared detection points.
We will instead test two ultrasonic sensors at successive positions along the entrance,
using distance changes and their order to estimate entry/exit. Alternate measurements to
limit acoustic interference; counting accuracy still needs validation. The existing
infrared code and configuration do not implement this change.

## Proposed socket reservations

**Provisional:** confirm exact module models/revisions, 3.3 V compatibility, interfaces
and Pi 5 driver support before wiring. The table assumes single-SIG Grove ultrasonic
rangers, a digital DHT11/DHT22, analog sound/light and a UART-mode Grove PN532.

| Component | Reserved socket | Signal/channel | Condition |
| --- | --- | --- | --- |
| Ultrasonic A — outside zone | D5 | BCM GPIO 5 | 3.3 V compatible single-SIG ranger |
| Ultrasonic B — inside zone | D18 | BCM GPIO 18 | Same as A |
| Temperature/humidity | D16 | BCM GPIO 16 | Digital DHT11/DHT22; I2C models need an I2C socket |
| Sound/noise | A0 | HAT ADC channel 0 | Analog module |
| Light | A2 | HAT ADC channel 2 | Analog module; I2C models need an I2C socket |
| NFC reader | UART/RPISER | BCM GPIO 14/15 | UART-mode PN532; verify Pi 5 serial routing/setup |
| LED bar — unconfirmed | D24 | Model-dependent control pins | Verify both signal assignments |
| Activity selector — unconfirmed | D22 | Model-dependent | Confirm selector/interface |

D labels use BCM numbering, not physical header pin numbers; A labels refer to HAT
ADC channels. Some modules use both signal wires: check the full socket pinout.
See manufacturer references for the [Base Hat](https://wiki.seeedstudio.com/Grove_Base_Hat_for_Raspberry_Pi/),
[ultrasonic ranger](https://wiki.seeedstudio.com/Grove-Ultrasonic_Ranger/) and
[NFC reader](https://wiki.seeedstudio.com/Grove_NFC/).
