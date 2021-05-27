# security_crawler_controller
## установка и запуск
Использовать python 3.7 или выше.
Предварительно требуется установить https://github.com/checkpoint-restore/criu
Для при тестировании использовалась версия из ветки criu-dev
Компиляция производилась со всеми доступными фичами

```
python -m venv env
source env/bin/activate
pip install -r requirements.txt 
python main_criu.py https://security-crawl-maze.app/javascript/frameworks/angular/ https://security-crawl-maze.app/ 100
```


