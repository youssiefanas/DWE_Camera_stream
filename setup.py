from setuptools import find_packages, setup
from glob import glob

package_name = 'dwe_camera_stream'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='anas',
    maintainer_email='anas@todo.todo',
    description='Low-latency H.264 UDP stream for DWE USB camera.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'sender = dwe_camera_stream.sender_node:main',
            'receiver = dwe_camera_stream.receiver_node:main',
            'camera = dwe_camera_stream.camera_node:main',
        ],
    },
)
