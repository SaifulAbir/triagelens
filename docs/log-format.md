# TriageLens log format

The log format and test framework are **invented for this project**. They don't imitate any real
vendor's format. The simulator writes this format; the preprocessing library reads it.

## Example

```
== TLRUN night-08 test=TC_HO_INTRA_FREQ_N3 stn=STN-03 fw=2.2 band=n3 start=2026-03-09T22:02:55Z ==
+0000.000 STN-03 w2 I FRAME  start TC_HO_INTRA_FREQ_N3 variant=INTRA_FREQ fw=2.2
+0000.070 STN-03 w2 I INSTR  SET:CELL:BAND n3
+0000.215 STN-03 w1 D INSTR  QUERY:RF:STATUS? -> OK temp=39.6C
+0001.000 STN-03 w9 D FRAME  keepalive seq=0
+0005.365 STN-03 w2 I PROTO  << RRCSetupRequest txn=0xeaa9
+0005.366 STN-03 w2 I CHECK  PASS expect=RRCSetupRequest within=2000ms took=159ms
+0005.401 STN-03 w2 I PROTO  >> RRCSetup txn=0xbfdd
+0007.920 STN-03 w2 I FRAME  end TC_HO_INTRA_FREQ_N3 result=PASS
== END result=PASS duration=0007.920s ==
```

## Structure

Every log file has exactly one header line, any number of event lines, and one footer line.

**Header**

```
== TLRUN <run_id> test=<test> stn=<station> fw=<firmware> band=<band> start=<UTC ISO 8601> ==
```

**Event line**

```
+<offset> <station> <thread> <level> <component> <message>
```

| Field | Format | Meaning |
|---|---|---|
| offset | `+SSSS.mmm` (4+ digits, 3 decimals) | Time since the test started |
| station | e.g. `STN-03` | Test station that ran the test |
| thread | `w<n>` | Worker thread that wrote the line |
| level | `D` `I` `W` `E` `F` | Debug, info, warning, error, fatal |
| component | padded to 6 characters | See below |
| message | free text to end of line | |

**Footer**

```
== END result=<PASS|FAIL|...> duration=<SSSS.mmm>s ==
```

## Components

| Component | Writes |
|---|---|
| `FRAME` | Test framework: start, end, keepalives, config |
| `PROTO` | Protocol messages. `>>` tester to device, `<<` device to tester |
| `INSTR` | Instrument commands and status polls |
| `CHECK` | Assertions: `PASS expect=<message> within=<limit>ms took=<actual>ms` |
| `HOST` | The station computer: disk, clock sync |

## Threads

| Thread | Content |
|---|---|
| `w2` | The test itself |
| `w1` | Instrument status polling, every ~2.5 s |
| `w4` | Host and framework warnings |
| `w9` | Keepalives, every second |

Lines from all threads are interleaved in time order.

## Things a parser must not assume

- **An `E` line does not mean the test failed.** Passing tests sometimes contain harmless errors,
  for example `E HOST NTP sync failed, retrying in 5s`. Only the footer and `CHECK` lines decide
  the result.
- **Offsets can have more than four integer digits** for tests longer than 9999 seconds.
- **Transaction IDs (`txn=0x....`) and temperatures are random** in every run. Normalise them
  before comparing two logs.
- **Messages can contain `==` and repeated spaces.**
