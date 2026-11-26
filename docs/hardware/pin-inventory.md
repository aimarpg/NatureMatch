# Wiring and pin inventory (Grove Base Hat)

## Current hardware decision

Reported hardware (15 November 2026): Raspberry Pi 5, Grove Base Hat for Raspberry Pi,
two ultrasonic distance sensors, temperature/humidity, sound, light and an NFC reader.
On 19 November 2026, the Grove 16x2 LCD (White on Blue) replaced the LED bar
specified for local feedback in the proposal. The activity selector is unconfirmed,
and NFC remains optional for the MVP.

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
| Grove 16x2 LCD (White on Blue) | Any socket marked I2C | I2C bus 1, address `0x3E`. SDA BCM 2, SCL BCM 3 | Use the Base Hat's 3.3 V Grove supply |
| Activity selector — unconfirmed | D22 | Model-dependent | Confirm selector/interface |

D labels use BCM numbering, not physical header pin numbers; A labels refer to HAT
ADC channels. Some modules use both signal wires: check the full socket pinout.
See manufacturer references for the [Base Hat](https://wiki.seeedstudio.com/Grove_Base_Hat_for_Raspberry_Pi/),
[ultrasonic ranger](https://wiki.seeedstudio.com/Grove-Ultrasonic_Ranger/) and
[NFC reader](https://wiki.seeedstudio.com/Grove_NFC/).

## Connecting the LCD

Shut down the Pi and disconnect its power supply. Connect the display to any of the
three sockets marked **I2C** on the Grove Base Hat using the four-pin Grove cable.
The sockets share the same bus. D24 is now free. The Grove cable carries yellow
(SCL, Pi header pin 5), white (SDA, pin 3), red (3.3 V) and black (GND).
The LCD's address `0x3E` is distinct from the Base Hat ADC's `0x04` or `0x08`.
See [Seeed's LCD specifications and wiring](https://wiki.seeedstudio.com/Grove-16x2_LCD_Series/).

Power up the Pi, enable I2C if needed, and follow the
[standalone LCD test](../../README.md#standalone-lcd-test).
