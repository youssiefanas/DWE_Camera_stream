# dwe_camera_stream

Low-latency H.264 video streaming for the **DWE StellarHD** (or any UVC) USB
camera over **mpegts/UDP**, wrapped as a ROS 2 (Jazzy) Python package.

- **Sender** node — grabs `/dev/videoX` via `ffmpeg`, encodes H.264 with
  zero-latency tuning, sends mpegts over UDP.
- **Receiver** node — decodes the UDP stream with a GStreamer pipeline
  (`udpsrc ! tsdemux ! h264parse ! avdec_h264 ! appsink`) and publishes
  `sensor_msgs/Image` on a ROS topic.

End-to-end latency is typically 1–2 frames on a LAN.

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

ROS 2 packages:

```bash
sudo apt install ros-jazzy-cv-bridge ros-jazzy-sensor-msgs
```

> `opencv-python` from pip is **not** built with GStreamer — use the apt
> `python3-opencv` that ships with ROS, or build OpenCV with
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

On the viewing host (receiver):

```bash
ros2 run dwe_camera_stream receiver \
    --ros-args \
    -p port:=1234 \
    -p topic:=/camera/image_raw
```

View in RViz (add an `Image` display on `/camera/image_raw`) or with:

```bash
ros2 run rqt_image_view rqt_image_view /camera/image_raw
```

---

## Nodes

### `sender` (`dwe_camera_stream.sender_node`)

Spawns `ffmpeg` and supervises it. Does not publish any topic.

| Parameter       | Default         | Description                                |
|-----------------|-----------------|--------------------------------------------|
| `device`        | `/dev/video0`   | V4L2 device path                           |
| `width`         | `1280`          | Capture width                              |
| `height`        | `720`           | Capture height                             |
| `fps`           | `30`            | Capture framerate                          |
| `input_format`  | `mjpeg`         | `mjpeg` or `yuyv422` (MJPEG = more FPS)    |
| `receiver_ip`   | `127.0.0.1`     | Destination IP for UDP stream              |
| `port`          | `1234`          | Destination UDP port                       |
| `bitrate`       | `4M`            | Target/max H.264 bitrate                   |
| `gop`           | `15`            | Keyframe interval (frames)                 |

### `receiver` (`dwe_camera_stream.receiver_node`)

Decodes the UDP stream and publishes `sensor_msgs/Image`.

| Parameter   | Default              | Description                                |
|-------------|----------------------|--------------------------------------------|
| `port`      | `1234`               | UDP port to listen on                      |
| `topic`     | `camera/image_raw`   | Image topic name                           |
| `frame_id`  | `camera`             | `header.frame_id` on published messages    |
| `pipeline`  | `""`                 | Override the full GStreamer pipeline       |

QoS: `BEST_EFFORT`, `KEEP_LAST`, depth `1`.

---

## Launch file

`launch/stream.launch.py` brings up both nodes with shared arguments:

```bash
ros2 launch dwe_camera_stream stream.launch.py \
    device:=/dev/video0 width:=1280 height:=720 fps:=30 \
    receiver_ip:=192.168.1.42 port:=1234 bitrate:=4M \
    topic:=/camera/image_raw
```

---

## Tuning tips

- **Still lagging?** Lower `gop` to `fps/2`, drop resolution, or switch to a
  wired link. UDP loss forces decoder to wait for the next keyframe.
- **Choppy / green frames?** Packet loss on Wi-Fi. Either increase `gop`
  (more keyframes → faster recovery) or move to Ethernet.
- **CPU-bound on Jetson?** Swap `libx264` for a hardware encoder
  (`h264_nvmpi` / `nvv4l2h264enc`) inside `sender_node.py`.
- **Check raw stream** without ROS:
  ```bash
  gst-launch-1.0 udpsrc port=1234 ! tsdemux ! h264parse ! avdec_h264 ! \
      videoconvert ! autovideosink sync=false
  ```

---

## Troubleshooting

| Symptom                                      | Fix                                                                 |
|----------------------------------------------|---------------------------------------------------------------------|
| `GStreamer: NO` in `cv2.getBuildInformation`| Use apt `python3-opencv`, not pip `opencv-python`.                  |
| `Cannot open /dev/video0`                    | `sudo usermod -aG video $USER` and re-login; check `v4l2-ctl --list-devices`. |
| Receiver opens but no frames                 | Firewall on UDP `1234`; `sudo ufw allow 1234/udp`.                  |
| `ffmpeg` exits immediately                   | Unsupported `width/height/fps`; run `v4l2-ctl -d /dev/video0 --list-formats-ext`. |

---

## License

MIT
# DWE_Camera_stream
