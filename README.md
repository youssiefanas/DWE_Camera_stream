# DWE Camera Stream

Low-latency H.264 video streaming for the **DWE StellarHD** (or any UVC) USB
camera over **mpegts / UDP**, wrapped as a ROS 2 (**Jazzy**) Python package.

Three nodes are provided:

- **Sender node** — grabs `/dev/videoX` via `ffmpeg`, encodes H.264 with
  zero-latency tuning, and sends an MPEG-TS stream over UDP.
- **Receiver node** — decodes the UDP stream with a GStreamer pipeline
  (`udpsrc → tsdemux → h264parse → avdec_h264 → appsink`) and publishes
  `sensor_msgs/Image` on a configurable ROS topic.
- **Camera node** — grabs `/dev/videoX` directly via V4L2 and publishes
  `sensor_msgs/Image` with no encoding, no UDP, and no extra latency.
  Use this when the camera is on the **same machine** as the subscriber.

End-to-end latency is typically **1–2 frames** on a wired LAN (sender/receiver)
or **< 1 frame** with the direct camera node.

---

## Architecture

```
┌──────────────────────────────────────────┐
│              Sender Machine              │
│                                          │
│  /dev/videoX ──► ffmpeg (libx264)        │
│                  - ultrafast preset      │
│                  - zerolatency tune      │
│                  - mpegts container      │
│                  - UDP output ──────────────┐
└──────────────────────────────────────────┘  │
                                              │  UDP (port 1234)
┌──────────────────────────────────────────┐  │
│            Receiver Machine              │  │
│                                          │  │
│  udpsrc ◄───────────────────────────────────┘
│    ▼                                     │
│  tsdemux → h264parse → avdec_h264        │
│    ▼                                     │
│  videoconvert → appsink (BGR)            │
│    ▼                                     │
│  ROS 2 publisher                         │
│    └─► /camera_dwe/image_raw             │
│        (sensor_msgs/Image, BEST_EFFORT)  │
└──────────────────────────────────────────┘
```

> Both nodes can also run on the **same machine** for loopback testing
> (default `receiver_ip` is `127.0.0.1`).

---

## Why this pipeline?

The previous V4L2+OpenCV approach buffered frames in userspace and lagged
behind real time. This package avoids that by:

1. Encoding directly in `ffmpeg` with `-fflags nobuffer -flags low_delay`,
   `-tune zerolatency`, `-bf 0 -refs 1`, a short GOP, and `-flush_packets 1`.
2. Using GStreamer on the receiver with
   `queue max-size-buffers=1 leaky=downstream` and
   `appsink drop=true max-buffers=1 sync=false` so stale frames are dropped
   instead of queued.
3. Publishing with `BEST_EFFORT` QoS, depth 1 — subscribers always get the
   newest frame.

---

## Dependencies

System packages (Ubuntu/Jetson):

```bash
sudo apt install ffmpeg v4l-utils \
    gstreamer1.0-tools gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly gstreamer1.0-libav \
    python3-opencv
```

### ROS 2 packages

```bash
sudo apt install ros-jazzy-cv-bridge ros-jazzy-sensor-msgs
```

> [!WARNING]
> `opencv-python` installed from pip is **not** built with GStreamer support.
> Use the apt `python3-opencv` that ships with ROS, or build OpenCV with
> `-DWITH_GSTREAMER=ON`. Verify with:
> ```python
> import cv2; print(cv2.getBuildInformation())
> ```
> and look for `GStreamer: YES`.

---

## Build

```bash
cd ~/jazzy_ws
colcon build --packages-select dwe_camera_stream
source install/setup.bash
```

---

## Usage

### Single machine (loopback test)

```bash
ros2 launch dwe_camera_stream stream.launch.py
```

This starts both the sender and receiver on the same machine with default
parameters (device `/dev/video0`, 1280×720 @ 30 fps, UDP port 1234).

### Two machines

On the camera host (Jetson / sender):

```bash
ros2 run dwe_camera_stream sender \
    --ros-args \
    -p device:=/dev/video0 \
    -p width:=1280 -p height:=720 -p fps:=30 \
    -p receiver_ip:=192.168.1.42 \
    -p port:=1234 \
    -p bitrate:=4M
```

**On the receiving host** (viewer):

```bash
ros2 run dwe_camera_stream receiver \
    --ros-args \
    -p port:=1234 \
    -p topic:=/camera_dwe/image_raw
```

### Viewing the stream

In **RViz2**: add an `Image` display on `/camera_dwe/image_raw`.

Or from the command line:

```bash
ros2 run rqt_image_view rqt_image_view /camera_dwe/image_raw
```

---

## Nodes

### `sender` (`dwe_camera_stream.sender_node`)

Spawns `ffmpeg` as a subprocess and monitors it with a watchdog timer.
If `ffmpeg` exits unexpectedly, the node shuts down. Does **not** publish any
ROS topic.

| Parameter      | Type   | Default       | Description                              |
|----------------|--------|---------------|------------------------------------------|
| `device`       | string | `/dev/video0` | V4L2 device path                         |
| `width`        | int    | `1280`        | Capture width in pixels                  |
| `height`       | int    | `720`         | Capture height in pixels                 |
| `fps`          | int    | `30`          | Capture framerate                        |
| `input_format` | string | `mjpeg`       | V4L2 pixel format (`mjpeg` or `yuyv422`) |
| `receiver_ip`  | string | `127.0.0.1`   | Destination IP for UDP stream            |
| `port`         | int    | `1234`        | Destination UDP port                     |
| `bitrate`      | string | `4M`          | Target / max H.264 bitrate               |
| `gop`          | int    | `15`          | Keyframe interval (number of frames)     |

> [!TIP]
> Use `input_format:=mjpeg` for higher FPS — most USB cameras deliver
> MJPEG at full resolution and frame rate, while raw `yuyv422` may cap
> at lower fps due to USB bandwidth.

### `receiver` (`dwe_camera_stream.receiver_node`)

Decodes the incoming mpegts/UDP stream using OpenCV's GStreamer backend
and publishes `sensor_msgs/Image` (BGR8 encoding).

| Parameter  | Type   | Default             | Description                            |
|------------|--------|---------------------|----------------------------------------|
| `port`     | int    | `1234`              | UDP port to listen on                  |
| `topic`    | string | `camera/image_raw`  | Published image topic name             |
| `frame_id` | string | `camera`            | `header.frame_id` on published images  |
| `pipeline` | string | `""`                | Override the full GStreamer pipeline    |

#### Published topics

| Topic                      | Type                 | QoS                              |
|----------------------------|----------------------|----------------------------------|
| `<topic>` (configurable)   | `sensor_msgs/Image`  | `BEST_EFFORT`, `KEEP_LAST(1)`   |

### `camera` (`dwe_camera_stream.camera_node`)

Direct V4L2 capture → ROS 2 publisher. No ffmpeg, no GStreamer, no UDP.
Opens the camera with OpenCV's V4L2 backend, sets a 1-buffer queue for
minimum latency, and publishes from a dedicated capture thread.

| Parameter  | Type   | Default              | Description                           |
|------------|--------|----------------------|---------------------------------------|
| `device`   | string | `/dev/video0`        | V4L2 device path                      |
| `width`    | int    | `1280`               | Capture width in pixels               |
| `height`   | int    | `720`                | Capture height in pixels              |
| `fps`      | int    | `30`                 | Capture framerate                     |
| `topic`    | string | `camera_dwe/image_raw` | Published image topic name          |
| `frame_id` | string | `camera`             | `header.frame_id` on published images |

#### Published topics

| Topic                      | Type                 | QoS                              |
|----------------------------|----------------------|----------------------------------|
| `<topic>` (configurable)   | `sensor_msgs/Image`  | `BEST_EFFORT`, `KEEP_LAST(1)`   |

#### Usage

```bash
# Via launch file
ros2 launch dwe_camera_stream camera.launch.py

# Or directly
ros2 run dwe_camera_stream camera \
    --ros-args \
    -p device:=/dev/video0 \
    -p width:=1280 -p height:=720 -p fps:=30 \
    -p topic:=camera_dwe/image_raw
```

---

## Launch file

`launch/stream.launch.py` brings up **both** nodes with shared launch
arguments:

```bash
ros2 launch dwe_camera_stream stream.launch.py \
    device:=/dev/video0 width:=1280 height:=720 fps:=30 \
    receiver_ip:=192.168.1.42 port:=1234 bitrate:=4M \
    topic:=/camera_dwe/image_raw
```

### Launch arguments

| Argument       | Default              | Description                          |
|----------------|----------------------|--------------------------------------|
| `device`       | `/dev/video0`        | V4L2 device path                     |
| `width`        | `1280`               | Capture width                        |
| `height`       | `720`                | Capture height                       |
| `fps`          | `30`                 | Capture framerate                    |
| `receiver_ip`  | `127.0.0.1`          | Destination IP                       |
| `port`         | `1234`               | UDP port                             |
| `bitrate`      | `4M`                 | H.264 bitrate                        |
| `topic`        | `camera_dwe/image_raw` | Image topic name                   |
| `run_sender`   | `true`               | Set `false` to skip the sender node  |
| `run_receiver` | `true`               | Set `false` to skip the receiver node|

> [!NOTE]
> `run_sender` and `run_receiver` arguments are declared but **not yet
> wired** to `IfCondition` in the launch file — both nodes always start.
> To run only one side, use `ros2 run` directly instead of the launch
> file, or add `IfCondition(LaunchConfiguration('run_sender'))` to the
> node definitions in `stream.launch.py`.

---

## Tuning tips

- **Still lagging?** Lower `gop` to `fps/2`, drop resolution, or switch to a
  wired link. UDP loss forces the decoder to wait for the next keyframe.
- **Choppy / green frames?** Packet loss on Wi-Fi. Either increase `gop`
  (more keyframes → faster recovery) or switch to Ethernet.
- **CPU-bound on Jetson?** Swap `libx264` for a hardware encoder
  (`h264_nvmpi` / `nvv4l2h264enc`) inside `sender_node.py`.
- **Check the raw stream** without ROS:
  ```bash
  gst-launch-1.0 udpsrc port=1234 ! tsdemux ! h264parse ! avdec_h264 ! \
      videoconvert ! autovideosink sync=false
  ```
- **List supported camera formats**:
  ```bash
  v4l2-ctl -d /dev/video0 --list-formats-ext
  ```

---
