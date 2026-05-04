@echo off
cd /d "%~dp0"
echo.
echo =======================================
echo  AUTO RENDER - GRAY HORIZONS ENTERPRISE
echo  Drop clips here. Double click. Done.
echo =======================================
echo.

mkdir output 2>nul

set COUNT=0

for %%f in (*.mp4) do (
  echo [RENDERING] %%f
  ffmpeg -y -i "%%f" ^
    -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,drawtext=text='We turn content into customers':fontcolor=white:fontsize=42:borderw=3:bordercolor=black:x=(w-text_w)/2:y=h-200" ^
    -c:v libx264 -preset veryfast -crf 23 -c:a copy "output\%%~nf_out.mp4"
  set /a COUNT+=1
  echo [DONE] output\%%~nf_out.mp4
  echo.
)

echo =======================================
echo  DONE - Check the output\ folder
echo =======================================
pause
