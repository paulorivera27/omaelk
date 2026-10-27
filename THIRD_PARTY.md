# Third-party notices

## elk-bledob — Will Cooke (MIT)

The command frames in `backend/elk.py` (power, colour, brightness, effect,
speed) and the effect-id table (`0x87`–`0x9c`) follow the ELK-BLEDOB protocol as
implemented in <https://github.com/8none1/elk-bledob>, which is distributed
under the MIT License:

```
Copyright (c) 2023 Will Cooke

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Dependencies (installed, not bundled)

| Package | License |
|---|---|
| [bleak](https://github.com/hbldh/bleak) | MIT |
| [NumPy](https://numpy.org) | BSD-3-Clause |

Optional helpers used through their command-line tools: `zenity` (LGPL),
`hyprpicker` (BSD-3-Clause).
