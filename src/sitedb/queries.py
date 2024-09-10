import requests
import logging
import json
from typing import Optional

prefix = "https://kdaminov.ru/olympbot"

session = requests.Session()


def all_activities() -> Optional[dict]:
    url = f"{prefix}/all_activities/"
    response = session.get(url)
    if response.status_code == 200:
        result = dict()
        for key, value in response.json().items():
            result[int(key)] = value
        return result
    return None


def all_subjects() -> Optional[dict]:
    url = f"{prefix}/all_subjects/"
    response = session.get(url)
    if response.status_code == 200:
        result = dict()
        for key, value in response.json().items():
            result[int(key)] = value
        return result
    return None


def post_filter(activities: list[int], subjects: list[int]) -> Optional[list[int]]:
    url = f"{prefix}/post_filter/?"
    for activity_id in activities:
        url += f"activity_id={activity_id}&"
    for subject_id in subjects:
        url += f"subject_id={subject_id}&"
    url = url[:-1]
    response = session.get(url)
    if response.status_code == 200:
        return response.json()
    return None


def event_filter(activity_id: int) -> Optional[list[int]]:
    url = f"{prefix}/event_filter/?activity_id={activity_id}"
    response = session.get(url)
    if response.status_code == 200:
        return response.json()
    return None


activity_data = all_activities()
assert activity_data is not None

subject_name_by_id = all_subjects()
subjects_id_by_name = dict()

for subject_id, name in subject_name_by_id.items():
    subjects_id_by_name[name] = subject_id
