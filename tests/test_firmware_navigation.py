from pathlib import Path
import subprocess


def test_manual_navigation_debounce_and_archive_refresh_isolation(tmp_path):
    root=Path(__file__).parents[1]
    exe=tmp_path/'navigation'
    subprocess.run(['c++','-std=c++11','-Wall','-Wextra','-Werror',
                    '-I',str(root/'firmware/include'),str(root/'tests/navigation_test.cpp'),
                    '-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=5)
