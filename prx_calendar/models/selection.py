from enum import Enum

class CalendarStatus(Enum):
    open = ("open","ღია")
    closed = ("closed","დახურული")


    @classmethod
    def selection(cls):
        return [member.value for member in cls]

class CalendarWeekdayGeo(Enum):
    monday = ('monday', 'ორშაბათი')
    tuesday = ('tuesday', 'სამშაბათი')
    wednesday = ('wednesday', 'ოთხშაბათი')
    thursday = ('thursday', 'ხუთშაბათი')
    friday = ('friday', 'პარასკევი')
    saturday = ('saturday', 'შაბათი')
    sunday = ('sunday', 'კვირა')

class CalendarMonthGeo(Enum):
    january = ('january', 'იანვარი')
    february = ('february', 'თებერვალი')
    march = ('march', 'მარტი')
    april = ('april', 'აპრილი')
    may = ('may', 'მაისი')
    june = ('june', 'ივნისი')
    july = ('july', 'ივლისი')
    august = ('august', 'აგვისტო')
    september = ('september', 'სექტემბერი')
    october = ('october', 'ოქტომბერი')
    november = ('november', 'ნოემბერი')
    december = ('december', 'დეკემბერი')


    @classmethod
    def selection(cls):
        return [member.value for member in cls]
