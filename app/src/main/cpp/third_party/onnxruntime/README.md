ONNX Runtime 1.17.1 C/C++ headers, copied without modification from the
`headers/` directory of the pinned `com.microsoft.onnxruntime:onnxruntime-android:1.17.1`
Android AAR. SHA-256 of `onnxruntime_c_api.h`:
`7e47eb78563da119f740dc0ddfda96800e779e0bcbd169a9a49e9c10746c4cd5`.

Copyright Microsoft Corporation; MIT license in `LICENSE`. The app does not
bundle the AAR's Java JNI library. Its C++ session calls the same ONNX Runtime
1.17.1 binary already contained in the pinned sherpa AAR.
