import os

import invoice
import money_fmt
import report

FIXTURES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_format_cents_behavior():
    assert money_fmt.format_cents(305) == "$3.05"
    assert money_fmt.format_cents(0) == "$0.00"
    assert money_fmt.format_cents(1000) == "$10.00"
    assert money_fmt.format_cents(7) == "$0.07"


def test_callers_still_work():
    assert report.render(305) == "Total: $3.05"
    assert invoice.line(1250) == "Amount due $12.50"


def test_report_does_not_redefine_helper():
    with open(os.path.join(FIXTURES, "report.py"), "r", encoding="utf-8") as f:
        source = f.read()
    assert "def format_cents" not in source, (
        "report.py must import format_cents from money_fmt rather than redefine it")


def test_invoice_does_not_redefine_helper():
    with open(os.path.join(FIXTURES, "invoice.py"), "r", encoding="utf-8") as f:
        source = f.read()
    assert "def format_cents" not in source, (
        "invoice.py must import format_cents from money_fmt rather than redefine it")
