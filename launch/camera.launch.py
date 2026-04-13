from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    args = [
        DeclareLaunchArgument('device',   default_value='/dev/video0'),
        DeclareLaunchArgument('width',    default_value='1280'),
        DeclareLaunchArgument('height',   default_value='720'),
        DeclareLaunchArgument('fps',      default_value='30'),
        DeclareLaunchArgument('topic',    default_value='camera_dwe/image_raw'),
        DeclareLaunchArgument('frame_id', default_value='camera'),
    ]

    camera = Node(
        package='dwe_camera_stream',
        executable='camera',
        name='dwe_camera_node',
        output='screen',
        parameters=[{
            'device':   LaunchConfiguration('device'),
            'width':    LaunchConfiguration('width'),
            'height':   LaunchConfiguration('height'),
            'fps':      LaunchConfiguration('fps'),
            'topic':    LaunchConfiguration('topic'),
            'frame_id': LaunchConfiguration('frame_id'),
        }],
    )

    return LaunchDescription(args + [camera])
