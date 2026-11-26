# Entrance counter validation

Use the [standalone people counter](../../README.md#standalone-ultrasonic-people-counter)
in a supervised, sheltered, single-file passage. Record the sensor placement,
thresholds, sampling settings, and known initial headcount. Keep the raw pair
log so the same run can be replayed when tuning the thresholds.

1. With both zones clear, verify stable background distances and no crossing
   events. Confirm that a person can trigger A alone, both zones, and B alone.
2. Have an observer log 20 complete crossings with timestamps and directions.
   Include 10 entries and 10 exits at slow, normal, and brisk walking speeds.
   Match each emitted event to one manual crossing and check its direction.
   The target is at least 18 of 20 correctly detected, with missed, extra, and
   wrong-direction events reported separately. Compare the final occupancy to
   the observer's tally.
3. Separately test a short pause, a pause beyond the crossing timeout,
   entering one zone and backing out, and reaching both zones before turning
   around. Expect one event for a complete crossing within the timeout and no
   event for the other attempts.
4. After a missed crossing or interruption, recheck the manual headcount and
   restart with that count and a clear passage. Record the result as an
   estimate for this entrance. Whole-area occupancy requires control of every
   entrance.
