from django import template

register = template.Library()

@register.filter
def currency(value, country):
    try:
        rates = {
            "IN": ("₹", 83.5),
            "US": ("$", 1),
            "UK": ("£", 0.79),
        }

        symbol, rate = rates.get(country, ("$", 1))

        return f"{symbol}{float(value) * rate:.2f}"
    except:
        return value


@register.filter
def inr(value):
    """
    INR filter for legacy category.html
    """
    try:
        return f"₹{float(value) * 90:.0f}"
    except:
        return value
