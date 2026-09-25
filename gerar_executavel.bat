@echo off
REM Gera o executavel do app "Gestao de Desempenho da Equipe"
REM Rode este arquivo na mesma pasta onde esta o gestao_desempenho.py

echo ============================================
echo  Instalando dependencias...
echo ============================================
pip install -r requirements.txt

echo.
echo ============================================
echo  Gerando o executavel (isso pode demorar um pouco)...
echo ============================================
pyinstaller --onefile --windowed --name GestaoDesempenho --collect-data matplotlib --hidden-import PIL._tkinter_finder gestao_desempenho.py

echo.
echo ============================================
echo  Pronto! O executavel esta em: dist\GestaoDesempenho.exe
echo  Copie esse arquivo para onde quiser usa-lo.
echo ============================================
pause
