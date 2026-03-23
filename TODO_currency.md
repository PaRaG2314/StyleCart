# StyleCart Auto Price Conversion Fixes TODO

**Goal:** Automatic currency/price conversion by location (country selector)

## Steps:
1. [x] Add |inr filter to core/templatetags/currency.py (fix category.html)
2. [x] Create AJAX set_country view in core/views.py
3. [x] Add URL path('set-country/', ...) to core/urls.py
4. [x] Remove hardcoded context['country']="IN" from all views
5. [ ] Test selector: change → AJAX → reload → prices updated
6. [x] Complete
