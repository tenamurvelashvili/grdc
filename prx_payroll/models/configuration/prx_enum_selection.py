from enum import Enum
from odoo import models, fields


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

class CalendarStatus(Enum):
    open = ("open","ღია")
    closed = ("closed","დახურული")


    @classmethod
    def selection(cls):
        return [member.value for member in cls]

class BankReports(Enum):
    bog = ("bog","საქართველო")
    tbc = ("tbc","თიბისი")

    @classmethod
    def selection(cls):
        return [member.value for member in cls]


class EarningUnit(Enum):
    day = ("day","დღე")
    hour = ("hour","სთ")
    unit = ("unit","ერთეული")
    shift = ("shift","ცვლა")
    half_time = ("half_time","ნახევარ განაკვეთი")

    @classmethod
    def selection(cls):
        return [member.value for member in cls]

class DeducationType(Enum):
    fix_amount = ('fix_amount','ფიქსირებული თანხა')
    percentage = ('percentage', 'პროცენტი')

    @classmethod
    def selection(cls):
        return [member.value for member in cls]

class DeducationBase(Enum):
    net_amount = ('net_amount','ხელზე ასაღები თანხიდან')
    gross_amount = ('gross_amount','დარიცხული თანხიდან')

    @classmethod
    def selection(cls):
        return [member.value for member in cls]

class WorksheetStatus(Enum):
    open = ('open','ღია')
    closed = ('closed', 'დახურული')
    posted = ('posted', 'დაპოსტილი')
    cancelled = ('cancelled', 'გაუქმებული')

    @classmethod
    def selection(cls):
        return [member.value for member in cls]

class WorksheetType(Enum):
    generated_by_user = ('generated_by_user','მომხმარებლის მიერ შექმნილი')
    generated = ('generated', 'გენერირებული')

    @classmethod
    def selection(cls):
        return [member.value for member in cls]


class CalculationType(Enum):
    worksheet = ('worksheet','ტაბელის შექმნა')
    worksheet_line = ('worksheet_line', 'ტაბელის სტრიქონების შექმნა')
    transaction = ('transaction', 'ხელფასის გატარებების გენერაცია')

    @classmethod
    def selection(cls):
        return [member.value for member in cls]

class TransactionType(Enum):
    earning = ('earning','ანაზღაურება')
    tax = ('tax', 'გადასახადი')
    deduction = ('deduction', 'დაქვითვა')
    transfer = ('transfer', 'გადარიცხვა')
    company_pension = ('company_pension', 'კომპანიის საპენსიონ')

    @classmethod
    def selection(cls):
        return [member.value for member in cls]

class RecordType(Enum):
    single_record_by_workday = ('single_record_by_workday','ერთი ჩანაწერით (სამუშაო დღის მიხედვით)')
    single_record_by_calendar = ('single_record_by_calendar', 'ერთი ჩანაწერით (კალენდარული დღის მიხედვით)')
    divide_work_day = ('divide_work_day', 'გაყოფილი დღეების მიხედვით (სამუშაო დღის მიხედვით)')
    divide_work_calendar = ('divide_work_calendar', 'გაყოფილი დღეების მიხედვით (კალენდარული დღის მიხედვით)')

    @classmethod
    def selection(cls):
        return [member.value for member in cls]


class PRXCalculationType(models.Model):
    _name = 'prx.calculation.type'
    _description = 'Calculation Type'
    _rec_name = 'name'

    company_id = fields.Many2one('res.company', string='კომპანია', default=lambda self: self.env.company, required=True)
    name = fields.Char(string='დასახელება')
    code = fields.Selection(CalculationType.selection())

class SalaryType(Enum):
    standard = ('standard', 'სტანდარტიული')
    avanse = ('avanse', 'ავანსი')
    one_time = ('one_time', 'ერთჯერადი')

    @classmethod
    def selection(cls):
        return [member.value for member in cls]

class BankTransactionReportType(Enum):
    transferred = ('transferred', 'გადარიცხული')
    non_transferred = ('non_transferred', 'გადაურიცხავი')
    all = ('all', 'ყველა')

    @classmethod
    def selection(cls):
        return [member.value for member in cls]