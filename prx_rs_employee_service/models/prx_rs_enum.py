from enum import Enum

class EmployeeStatusSelectionList(Enum):
    cancel = ("0",'შეწყვეტილი')
    active = ("1",'აქტიური')
    suspended = ("-1",'შეჩერებული')

    @classmethod
    def selection(cls):
        return [member.value for member in cls]

class WorkTypeList(Enum):
    full_time = ('1','ნახევარი განაკვეთი')
    half_time = ('2','სრული განაკვეთი')

    @classmethod
    def selection(cls):
        return [member.value for member in cls]

class GenderList(Enum):
    man = ('1','მამაკაცი')
    women = ('2','ქალი')

    @classmethod
    def selection(cls):
        return [member.value for member in cls]

class EmployeeStatus(Enum):
    cancel = ('cancel',0)
    active = ('active',1)
    suspended = ('suspended',-1)

    @classmethod
    def selection(cls):
        return { member.value[0]: member.value[1] for member in cls }

class Gender(Enum):
    man = ('male',1)
    women = ('female',2)

    @classmethod
    def selection(cls):
        return { member.value[0]: member.value[1] for member in cls }

class WorkType(Enum):
    full_time = ('full',1)
    half_time = ('half',2)

    @classmethod
    def selection(cls):
        return { member.value[0]: member.value[1] for member in cls }

class AuthMethod(Enum):
    basic = ("0","basic")
    oauth = ("oauth", "OAuth")

    @classmethod
    def selection(cls):
        return [member.value for member in cls]