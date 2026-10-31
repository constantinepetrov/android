The optional, isolated Android ABI experiment builds libffi 3.4.6 from commit
`3d0ce1e6fcf19f853894862abcbac0ae78a7be60` of https://github.com/libffi/libffi.
The upstream MIT-style license is copied from the checked-out source into the
APK at `assets/licenses/libffi.txt` by the experiment workflow. Free Pascal's
`ffi.pp` and `ffi.manager.pp` are built from the official FPC 3.2.2 source
checkout and remain subject to that distribution's COPYING.FPC terms.
The experiment does not alter the main game's bundled dependencies.
