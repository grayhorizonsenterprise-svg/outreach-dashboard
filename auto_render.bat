@echo off

mkdir output 2>nul

for %%f in (*.mp4) do (
  ffmpeg -y -i "%%f" ^
  -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,drawtext=fontfile='C\:/Windows/Fonts/arial.ttf':text='GET MORE CUSTOMERS':fontcolor=white:fontsize=72:x=(w-text_w)/2:y=200:box=1:boxcolor=black@0.6:boxborderw=20,drawtext=fontfile='C\:/Windows/Fonts/arial.ttf':text='Most businesses get ignored online':fontcolor=white:fontsize=58:x=(w-text_w)/2:y=900:box=1:boxcolor=black@0.6:boxborderw=20,drawtext=fontfile='C\:/Windows/Fonts/arial.ttf':text='We fix that':fontcolor=yellow:fontsize=64:x=(w-text_w)/2:y=1500:box=1:boxcolor=black@0.7:boxborderw=25" ^
  -c:v libx264 -preset veryfast -crf 23 -c:a copy "output\%%~nf_out.mp4"
)

echo Done.
pause