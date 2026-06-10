from setuptools import find_packages, setup

package_name = 'soa_apps'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ubuntu',
    maintainer_email='42076119+htchr@users.noreply.github.com',
    description='TODO: Package description',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'go_to_joint_states = soa_apps.go_to_joint_states:main',
            'go_to_poses = soa_apps.go_to_poses:main',
            'pick_by_position = soa_apps.pick_by_position:main',
            'hover_to_object = soa_apps.hover_to_object:main',
            'grasp_state_machine = soa_apps.state_machine:main',
            'move_arm_to_height = soa_apps.move_arm_to_height:main',
            'grasp_sequencer = soa_apps.grasp_sequencer:main',
        ],
    },
)
