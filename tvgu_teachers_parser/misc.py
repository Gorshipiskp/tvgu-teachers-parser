import json
import re
from dataclasses import dataclass
from typing import Optional

import bs4

from .config import NON_DIGITS_PATTERN, DIGITS_PATTERN, TEACHER_FULLNAME_PATTERN, TEACHER_NAME_PARTS


@dataclass(frozen=True, kw_only=True)
class Teacher:
    name: str
    surname: str
    patronymic: str
    initials: str
    current_job: str
    teaching_disciplines: list[str]
    level_education: str
    direction_education: str
    jobs: list[str]
    degrees: list[str]
    academ_stats: list[str]
    rewards: list[str]
    qualify_ups: list[str]
    experience_age: int
    phone: str
    phone_additional_code: str
    email: str
    teaching_programs: list[str]


def truly_capitalize(text: str) -> str:
    if not text:
        return ""
    return text[0].upper() + text[1:]


def flat(list_of_lists: list[list]) -> list:
    return [item for sublist in list_of_lists for item in sublist]


def remove_whitespaces(text: str) -> str:
    text = text.replace("\xa0", " ").strip()

    while "  " in text:
        text = text.replace("  ", " ")

    return text


def split_n_strip_n_capitalize(text: str, *splitters: str, additional_func: callable = lambda x: x) -> list[str]:
    # Защищаем разделений от разграничителей внутри скобок
    if splitters:
        splitted = re.split(r"(?:%s)(?![^()]*\))" % "|".join(map(re.escape, splitters)), text)
    else:
        splitted = [text]

    return list(filter(
        lambda x: bool(x),
        (truly_capitalize(remove_whitespaces(additional_func(element).strip())) for element in splitted)
    ))


#  Бывают кнопки "Показать", если текста много, так что вытягиваем из модалки инфу
def handle_possible_modal(tag: bs4.element.Tag, *splitters: str, additional_func: callable = lambda x: x) -> list[str]:
    modal_container: Optional[bs4.element.Tag] = tag.find(class_="showpart-container-modal")

    if modal_container is None:
        contents: list[str] = split_n_strip_n_capitalize(tag.text, *splitters, additional_func=additional_func)
    else:
        contents: list[str] = [
            truly_capitalize(li.text.strip().strip(";")) for li in modal_container.find_all("li")
        ]

        if not contents:
            p: bs4.element.Tag = modal_container.find("p")

            if p is None:
                contents = split_n_strip_n_capitalize(modal_container.text, *splitters,
                                                      additional_func=additional_func)
            else:
                contents = split_n_strip_n_capitalize(p.text, *splitters, additional_func=additional_func)
    return contents


#  Код плотный, но иначе будет слишком много бессмысленных переменных
def parse_teacher_record(teacher_record: bs4.element.Tag) -> Teacher:
    name: str = teacher_record.find(itemprop="fio").text.strip()

    parts: list[str] = re.findall(TEACHER_FULLNAME_PATTERN, name)[0]

    name_parts: dict[str, str] = dict(zip(TEACHER_NAME_PARTS, [part.capitalize() for part in parts]))

    #  В формате "Фамилия И.О."
    initials: str = f"{name_parts['surname']} {name_parts['name'][0]}.{name_parts['patronymic'][0]}.".strip()

    current_job_tag: bs4.element.Tag = teacher_record.find(itemprop="post")
    current_job: str = handle_possible_modal(current_job_tag, ",", ";")[0]

    teaching_disciplines_tag: bs4.element.Tag = teacher_record.find(itemprop="teachingDiscipline")
    teaching_disciplines: list[str] = handle_possible_modal(teaching_disciplines_tag, ",", ";")

    teaching_level_tag: bs4.element.Tag = teacher_record.find(itemprop="teachingLevel")
    educations_n_jobs: list[str] = split_n_strip_n_capitalize(
        teaching_level_tag.encode_contents().decode("UTF-8").replace("</br>", ""), "<br>"
    )
    educations_n_jobs = flat(
        split_n_strip_n_capitalize(education, ",", ";", ". ", additional_func=lambda x: x.replace("\"", "").strip("."))
        for education in educations_n_jobs
    )

    level_education: str = educations_n_jobs.pop(0)
    direction_education: str = educations_n_jobs.pop(0)
    jobs: list[str] = educations_n_jobs

    degree_tag: bs4.element.Tag = teacher_record.find(itemprop="degree")
    degrees: list[str] = handle_possible_modal(degree_tag, ",", ";")

    academ_stat_tag: bs4.element.Tag = teacher_record.find(itemprop="academStat")
    academ_stats: list[str] = handle_possible_modal(academ_stat_tag, ",")

    rewards_tag: bs4.element.Tag = academ_stat_tag.find_next("td")
    rewards: list[str] = handle_possible_modal(rewards_tag, ",", ";")

    qualify_up_tag: bs4.element.Tag = teacher_record.find(itemprop="qualification")
    qualify_ups: list[str] = handle_possible_modal(qualify_up_tag, ",", ";")

    exp_age_tag: bs4.element.Tag = teacher_record.find(itemprop="specExperience")
    exp_age_str: str = handle_possible_modal(exp_age_tag)[0]

    try:
        exp_age: int = int(re.findall(DIGITS_PATTERN, exp_age_str)[0])
    except IndexError:
        exp_age = 0

    phone_tag: bs4.element.Tag = exp_age_tag.find_next("td")
    phones: list[str] = handle_possible_modal(phone_tag, ",", ";")
    phone: str = phones[0] if phones else None
    phone_with_add_code: Optional[list[str]] = [
        re.sub(NON_DIGITS_PATTERN, "", phone_part) for phone_part in phone.split("доб")
    ] if phone else None
    phone: Optional[str] = phone_with_add_code[0] if phone_with_add_code else None
    phone_additional_code: Optional[str] = phone_with_add_code[1] if phone and len(phone_with_add_code) > 1 else None

    email_tag: bs4.element.Tag = phone_tag.find_next("td")
    emails: list[str] = handle_possible_modal(email_tag, ",", ";")
    email: str = emails[0] if emails else None

    teaching_programs_tag: bs4.element.Tag = teacher_record.find(itemprop="teachingOp")
    teaching_programs: list[str] = handle_possible_modal(teaching_programs_tag, ";")

    return Teacher(
        name=name_parts["name"],
        surname=name_parts["surname"],
        patronymic=name_parts["patronymic"],
        initials=initials,
        current_job=current_job,
        teaching_disciplines=teaching_disciplines,
        level_education=level_education,
        direction_education=direction_education,
        jobs=jobs,
        degrees=degrees,
        academ_stats=academ_stats,
        rewards=rewards,
        qualify_ups=qualify_ups,
        experience_age=exp_age,
        phone=phone,
        phone_additional_code=phone_additional_code,
        email=email,
        teaching_programs=teaching_programs
    )


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        return obj.__dict__
