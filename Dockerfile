FROM snakepacker/python:all as builder

RUN python3.11 -m venv /usr/share/python3/app \
     && /usr/share/python3/app/bin/pip install -U pip

COPY . .

RUN /usr/share/python3/app/bin/pip install -Ur requirements.txt \
    && python3.11 setup.py sdist \
    && /usr/share/python3/app/bin/pip install ./dist/* \
    && /usr/share/python3/app/bin/pip check

FROM snakepacker/python:3.11 as api

COPY --from=builder /usr/share/python3/app /usr/share/python3/app

RUN ln -snf /usr/share/python3/app/bin/* /usr/local/bin/

WORKDIR /usr/local/bin
