from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    args = [
        DeclareLaunchArgument('device', default_value='/dev/video0'),
        DeclareLaunchArgument('width', default_value='1280'),
        DeclareLaunchArgument('height', default_value='720'),
        DeclareLaunchArgument('fps', default_value='30'),
        DeclareLaunchArgument('receiver_ip', default_value='127.0.0.1'),
        DeclareLaunchArgument('port', default_value='1234'),
        DeclareLaunchArgument('bitrate', default_value='4M'),
        DeclareLaunchArgument('topic', default_value='camera_dwe/image_raw'),
        DeclareLaunchArgument('run_sender', default_value='true'),
        DeclareLaunchArgument('run_receiver', default_value='true'),
    ]

    sender = Node(
        package='dwe_camera_stream',
        executable='sender',
        name='dwe_camera_sender',
        output='screen',
        parameters=[{
            'device': LaunchConfiguration('device'),
            'width': LaunchConfiguration('width'),
            'height': LaunchConfiguration('height'),
            'fps': LaunchConfiguration('fps'),
            'receiver_ip': LaunchConfiguration('receiver_ip'),
            'port': LaunchConfiguration('port'),
            'bitrate': LaunchConfiguration('bitrate'),
        }],
        condition=None,
    )

    receiver = Node(
        package='dwe_camera_stream',
        executable='receiver',
        name='dwe_camera_receiver',
        output='screen',
        parameters=[{
            'port': LaunchConfiguration('port'),
            'topic': LaunchConfiguration('topic'),
        }],
    )

    return LaunchDescription(args + [sender, receiver])
