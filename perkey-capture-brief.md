# Reverse-engineering brief: per-key RGB on Acer Predator Triton 500 (PT515-52)

Handoff document for a Claude session running in WSL on the Windows side of this
dual-boot machine. Goal: capture and decode the USB protocol PredatorSense uses
for **per-key / custom RGB** on the internal keyboard, so we can replicate it on
Linux. Everything below marked "known" was already reverse-engineered on the
Linux side and verified on this exact unit.

## The device

- Internal keyboard controller: **Darfon, USB VID `0x0d62` PID `0x7cb1`**
  (product string "USB-HID Keyboard", shows up as HOLTEK in some tooling).
- 4 USB interfaces: 0–2 are keys/media, **interface 3 is the RGB/vendor channel**.
- HID report descriptor of interface 3 (dumped on Linux):

  ```
  06 01 ff 09 01 a1 01 15 00 26 ff 00 75 08 95 40
  09 20 81 02 09 21 91 02 09 22 95 08 b1 02 c0
  ```

  Decoded: vendor usage page 0xFF01; **64-byte INPUT report** (usage 0x20),
  **64-byte OUTPUT report** (usage 0x21), **8-byte FEATURE report** (usage 0x22).
  No report IDs. The 8-byte feature report is fully understood (below). The
  64-byte output report is the prime suspect for per-key data — this is the
  classic Darfon/Chicony pattern (per-key frames streamed as 64-byte writes).

## Known protocol (already working on Linux)

Static preset command = the 8-byte **feature** report on interface 3
(SET_REPORT, bmRequestType 0x21, bRequest 0x09, wValue 0x0300, wIndex 3):

```
[0x08, 0x00, mode, 0x05, brightness, color, 0x00, checksum]
  mode:       0x01 = static (other modes unknown — animations are a bonus target)
  brightness: 0x00–0x64; firmware saturates: ≥ ~0x32 (50) renders identical to max
  color:      firmware palette preset 0–8
              0=dark red 1=orange 2=teal 3=yellow-green 4=blue 5=light green
              6=purple 7=white 8=red
  checksum:   (0xFF - sum(first 7 bytes)) & 0xFF
```

Example (the payload this unit runs on Linux, red @ brightness 50):
`08 00 01 05 32 08 00 b7`. **Use this as a fingerprint** to locate the device's
traffic in the capture and as a known-good reference.

Also known: pressing Fn+F7/F8 emits a vendor **input** report on interface 2:
`04 7d` (down) / `04 7c` (up). PredatorSense reacts to those by re-sending a
lighting command — expect to see that pattern in captures too; it's noise for
our purpose, already understood.

## Unknowns (what we're after, in priority order)

1. **Per-key addressing**: how a single key is identified (matrix row/col? linear
   index? scancode?) and how its RGB value is encoded.
2. **Arbitrary RGB values**: presets 0–8 take a palette index; per-key mode
   presumably carries real 3-byte RGB. Confirm byte order (RGB vs GRB etc.).
3. **Frame structure**: header/start command, number of 64-byte packets per full
   frame, terminator/commit command, any checksum per packet.
4. **Handshake**: what PredatorSense sends/reads at startup (GET_REPORTs, version
   queries via the 64-byte input report).
5. Bonus: other `mode` values (breathing, wave...) and whether brightness works
   differently in per-key mode (the 0–50 saturation may be preset-specific).

## Capture setup (Windows side)

WSL2 cannot sniff host USB — the capture must run on native Windows:

1. Install **Wireshark + USBPcap** (bundled in the Wireshark installer; needs a
   reboot after driver install).
2. Find the keyboard: `USBPcapCMD.exe` lists root hubs and attached devices —
   pick the root hub containing VID 0D62 PID 7CB1 (it's the internal keyboard,
   always attached). Capture that hub only, to keep files small.
3. In Wireshark, useful display filters:
   - `usb.idVendor == 0x0d62` (only matches descriptor packets — use it once to
     learn the device address, e.g. `2.5`)
   - then `usb.device_address == 5` (adjust) for everything from that device
   - `usb.transfer_type == 0x02 && usb.setup.bRequest == 0x09` → SET_REPORTs
   - 64-byte OUTPUT data (interrupt or control) to interface 3 = the target.
4. Save as `.pcapng`. WSL can read it from `/mnt/c/...` and analyze with `tshark`.

Fallback if USBPcap misbehaves: API-level HID sniffing (e.g. hooking
`HidD_SetOutputReport`/`WriteFile` with Frida on PredatorSense) — but try
USBPcap first, it's usually enough.

## Experiment script (run with capture running; keep a timestamped action log!)

The single most valuable thing besides the pcap is a **log of what was clicked
and when** (down to the second), so packets can be matched to actions. Between
experiments, insert a *marker*: set static preset red — it produces the known
8-byte `08 00 01 05 xx 08 00 ck` and acts as a separator in the capture.

0. Start capture **before** launching PredatorSense → captures the startup
   handshake/queries.
1. Idle 5 s. Note PredatorSense version and any keyboard firmware version shown.
2. Static preset red (marker #1).
3. Per-key/custom mode: set **ALL keys to pure red `FF0000`**, apply.
4. Change **only ESC** to pure blue `0000FF`, apply. (Diff vs step 3 reveals
   addressing.)
5. Change **only F1** to pure green `00FF00`, apply. (Adjacent key → confirms
   ordering.)
6. Set one key (e.g. `A`) to the distinctive value **`#123456`**, apply. (Literal
   `12 34 56` — or a permutation — should be findable in the payload, revealing
   byte order.)
7. Marker: static red again.
8. In per-key mode, brightness ramp: 0 → 25 → 50 → 75 → 100 (one apply each,
   log the times). Checks whether the 0–50 saturation also applies here.
9. If PredatorSense has animated effects (wave/breathing/ripple): activate one
   or two, log which. (Maps more `mode` bytes.)
10. Save the profile / hit whatever "apply permanently" exists → may reveal a
    commit/persist-to-flash command. Also note whether the lighting survives
    with PredatorSense killed.
11. Stop capture.

If PredatorSense on this model only offers the 9 presets and **no** per-key UI,
log that (screenshot) — it means per-key needs a different tool (Darfon OEM
utility) and the capture of presets/animations is still valuable.

## Deliverables back to the Linux side

- The `.pcapng` file(s).
- The timestamped action log.
- PredatorSense version + firmware version if visible.
- Ideally a first-pass analysis from WSL: for each experiment step, the hex of
  the reports sent to interface 3, e.g.:

  ```bash
  tshark -r capture.pcapng -Y 'usb.device_address == N && usb.data_len > 0' \
         -T fields -e frame.time_relative -e usb.endpoint_address -e usb.capdata
  ```

  A diff of step 3 vs step 4 vs step 5 payloads is the jackpot: it isolates the
  per-key addressing and RGB encoding in one shot.

Findings will be replayed on Linux via HIDIOCSFEATURE / write() on
`/dev/hidraw3` (interface 3) — no Windows dependency after this one capture.
