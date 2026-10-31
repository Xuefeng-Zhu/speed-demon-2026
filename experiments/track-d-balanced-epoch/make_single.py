from pathlib import Path
s=Path(__file__).with_name("meeting.rs").read_text()
old="let threads = thread::available_parallelism().map_or(1, |n| n.get());"
assert s.count(old)==1
Path("/tmp/sd-balanced-epoch-single.rs").write_text(s.replace(old,"let threads = 1;"))
