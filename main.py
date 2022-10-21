import base64
from datetime import datetime
from functools import partial
import json
import traceback
import requests
from csv_ical import Convert
from tqdm.contrib.concurrent import process_map
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import csv


def main():
    retry_strategy = Retry(total=3, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    timetables = get_timetables(session)
    consolidated_csv = []
    timetable_handler = partial(get_timetable, session)
    consolidated_csv = process_map(timetable_handler, timetables["data"])
    consolidated_csv = [row for row in consolidated_csv if row != []]
    final_list = []
    for timetable in consolidated_csv:
        if timetable is not None:
            final_list.extend(timetable)
    with open("output.csv", "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(final_list)


def get_timetables(session: requests.Session):
    url = "https://mytimetable.leeds.ac.uk/overview/pos/data"
    timetable_list = session.get(url, params={"d": "202223"})
    return timetable_list.json()


def get_timetable(session: requests.Session, timetable: dict):
    try:
        converter = Convert()
        timetable_full = get_timetable_data(session, timetable)
        output_file_name = f"output/{timetable['name'].replace('/', '_')}.ical"
        with open(output_file_name, "w", newline="") as file:
            file.write(timetable_full)
        converter.read_ical(output_file_name)
        converter.make_csv()
        event_list = converter.csv_data
        [event.append(timetable["name"]) for event in event_list]
        for index, event in enumerate(event_list):
            event_list[index] = [data.replace("\n", " ") for data in event]
        return event_list
    except Exception as e:
        with open(f"errors/{datetime.now().timestamp()}.log", "a") as file:
            file.write(traceback.format_exc())
            file.write(json.dumps(timetable, indent=4))


def get_timetable_data(session: requests.Session, timetable: dict):
    url = "https://mytimetable.leeds.ac.uk/ical"
    timetable_full = session.get(
        url,
        params={
            "63484db6": "",
            "group": "false",
            "timetable": b"!" + encode_for_url(timetable["key"]),
            "eu": encode_for_url("el18gs@leeds.ac.uk"),
            "h": "fau3pP3eChge_wm73rkHMTQAWKLxQDbfu3regfeuK7U=",
        },
    )
    if timetable_full.status_code == 200:
        return timetable_full.text
    else:
        raise Exception(timetable, timetable_full)


def encode_for_url(string: str):
    string_ascii = str.encode(string)
    return base64.b64encode(string_ascii)


if __name__ == "__main__":
    main()
