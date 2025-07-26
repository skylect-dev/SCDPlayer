for %%F in (*.wav) do (
copy test.scd %%~nF.scd 
MusicEncoder.exe %%~nF.scd %%F
del %%~nF.scd 
)
pause