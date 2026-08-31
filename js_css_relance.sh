#!/bin/bash

docker-compose exec web python3 manage.py collectstatic --noinput
