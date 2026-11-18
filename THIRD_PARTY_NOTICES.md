# Third-party components

| Component | Use | License |
|---|---|---|
| RTMPose-l (OpenMMLab / MMPose, `rtmpose-l_simcc-body7_pt-body7_420e-256x192`) | High-accuracy body keypoints (`public/model/rtm.*.wasm`, ONNX split into parts, weights stored as float16) | Apache-2.0 |
| MediaPipe Pose Landmarker (Google) | Person tracking and fast keypoints (`public/model/pose_landmarker.wasm`, `public/wasm/`, `public/vendor/vision_*`) | Apache-2.0 |
| ONNX Runtime Web 1.20.1 (Microsoft) | Runs RTMPose in the browser (`public/vendor/ort*`, `public/ort/`) | MIT |
| mp4-muxer 5.2.1 | Writes the comparison video file | MIT |

The RTMPose ONNX file was converted from the official OpenMMLab release: weights are stored as float16 with Cast nodes so the file is half the size; results were checked against the original model.
