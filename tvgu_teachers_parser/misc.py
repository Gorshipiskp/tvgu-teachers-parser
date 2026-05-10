import json
import re
from dataclasses import dataclass
from typing import Optional, Callable, TypeVar, Any

from bs4 import Tag

from .config import NON_DIGITS_PATTERN, DIGITS_PATTERN, TEACHER_FULLNAME_PATTERN, TEACHER_NAME_PARTS


@dataclass(frozen=True, kw_only=True)
class Teacher:
    name: str
    surname: str
    patronymic: str
    initials: str
    lms_profile_link: Optional[str]
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
    phone: Optional[str]
    phone_additional_code: Optional[str]
    email: str
    teaching_programs: list[str]

    def _identify(self) -> tuple[str, str, str, str | None, str | None, int, str, str, str]:
        return (
            self.name,
            self.surname,
            self.patronymic,
            self.phone,
            self.phone_additional_code,
            self.experience_age,
            self.level_education,
            self.direction_education,
            self.email
        )

    def __hash__(self) -> int:
        return hash(self._identify())

    def __eq__(self, other) -> bool:
        if isinstance(other, Teacher):
            return self._identify() == other._identify()
        return NotImplemented


def truly_capitalize(text: str) -> str:
    if not text:
        return ""
    return text[0].upper() + text[1:]


T = TypeVar("T")


def flat(list_of_lists: list[list[T]]) -> list[T]:
    return [item for sublist in list_of_lists for item in sublist]


def remove_whitespaces(text: str) -> str:
    text: str = text.replace("\xa0", " ").strip()

    while "  " in text:
        text = text.replace("  ", " ")

    return text


def split_n_strip_n_capitalize(text: str, *splitters: str,
                               additional_func: Callable[..., str] = lambda x: x) -> list[str]:
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
def handle_possible_modal(tag: Tag, *splitters: str,
                          additional_func: Callable[..., str] = lambda x: x) -> list[str]:
    modal_container: Optional[Tag] = tag.find(class_="showpart-container-modal")

    if modal_container is None:
        contents: list[str] = split_n_strip_n_capitalize(tag.text, *splitters, additional_func=additional_func)
    else:
        contents: list[str] = [
            truly_capitalize(li.text.strip().strip(";")) for li in modal_container.find_all("li")
        ]

        if not contents:
            p: Tag = modal_container.find("p")

            if p is None:
                contents = split_n_strip_n_capitalize(modal_container.text, *splitters,
                                                      additional_func=additional_func)
            else:
                contents = split_n_strip_n_capitalize(p.text, *splitters, additional_func=additional_func)
    return contents


#  Код плотный, но иначе будет слишком много бессмысленных переменных
#  UPD: Примерно 23.04.26 страница с преподавателями изменила структуру
def parse_teacher_record(teacher_record: Tag) -> Teacher:
    # Получаем все ячейки строки
    cells = teacher_record.find_all("td")

    # --- ФИО и LMS-ссылка (индекс 1) ---
    fullname_cell = cells[1]
    fullname = fullname_cell.get_text(strip=True)
    # Извлекаем ссылку на LMS, если есть
    a_tag = fullname_cell.find("a")
    lms_profile_link = a_tag.get("href") if a_tag else None

    # Разбиваем ФИО на части (используя те же регулярки, что и раньше)
    parts = re.findall(TEACHER_FULLNAME_PATTERN, fullname)[0]
    name_parts = dict(zip(
        TEACHER_NAME_PARTS,
        [re.sub(r'-(\w)', lambda m: '-' + m.group(1).upper(), part.capitalize())
         for part in parts]
    ))
    initials = f"{name_parts['surname']} {name_parts['name'][0]}.{name_parts['patronymic'][0]}."

    # --- Должность (индекс 2) ---
    current_job = handle_possible_modal(cells[2], ",", ";")[0]

    # --- Преподаваемые дисциплины (индекс 3) ---
    teaching_disciplines = handle_possible_modal(cells[3], ",", ";")

    # --- Образование (индекс 4) ---
    # Копируем логику из старой версии: сначала разбиваем по <br>, потом по запятым и точкам
    educations_n_jobs = split_n_strip_n_capitalize(
        cells[4].encode_contents().decode("UTF-8").replace("</br>", ""),
        "<br>"
    )
    educations_n_jobs = flat([
        split_n_strip_n_capitalize(e, ",", ";", ". ",
                                   additional_func=lambda x: x.replace("\"", "").strip("."))
        for e in educations_n_jobs
    ])
    level_education = educations_n_jobs.pop(0)
    direction_education = educations_n_jobs.pop(0)
    jobs = educations_n_jobs

    # --- Учёная степень (индекс 5) ---
    degrees = handle_possible_modal(cells[5], ",", ";")

    # --- Учёное звание (индекс 6) ---
    academ_stats = handle_possible_modal(cells[6], ",")

    # --- Награды (индекс 7) ---
    rewards = handle_possible_modal(cells[7], ",", ";")
    rewards = [r for r in rewards if r and r.lower() != "нет"]

    # --- Повышение квалификации (индекс 8) ---
    qualify_ups = handle_possible_modal(cells[8], ",", ";")

    # --- Стаж (индекс 10) ---
    exp_age_str = handle_possible_modal(cells[10])[0]
    try:
        exp_age = int(re.findall(DIGITS_PATTERN, exp_age_str)[0])
    except IndexError:
        exp_age = 0

    # --- Телефон (индекс 11) ---
    phone_cell = cells[11]
    phones = handle_possible_modal(phone_cell, ",", ";")
    phone = phones[0] if phones else None
    if phone:
        phone_with_add_code = [
            re.sub(NON_DIGITS_PATTERN, "", part)
            for part in re.split(r"(?:доб)|(?:доп)", phone)
        ]
        phone = phone_with_add_code[0]
        phone_additional_code = phone_with_add_code[1] if len(phone_with_add_code) > 1 else None
    else:
        phone_additional_code = None

    # --- Email (индекс 12) ---
    emails = handle_possible_modal(cells[12], ",", ";")
    email = emails[0] if emails else None

    # --- Образовательные программы (индекс 13) ---
    teaching_programs = handle_possible_modal(cells[13], ";")

    return Teacher(
        name=name_parts["name"],
        surname=name_parts["surname"],
        patronymic=name_parts["patronymic"],
        initials=initials,
        lms_profile_link=lms_profile_link,
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
    def default(self, obj) -> dict[str, Any]:
        return obj.__dict__
