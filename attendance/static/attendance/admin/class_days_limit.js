/*
 * Class group admin: limit the weekday checkboxes to "Class days per week".
 *
 * - When the limit is reached, the unticked days are disabled.
 * - Unticking a day makes the others selectable again.
 * - If the limit is lowered below the current selection, nothing is
 *   unticked automatically; the hint asks the admin to untick days.
 *
 * This is only for convenience. ClassGroup.clean() on the server still
 * rejects a save unless exactly the right number of days is ticked.
 */
(function () {
    'use strict';

    var DAY_FIELDS = [
        'monday', 'tuesday', 'wednesday', 'thursday',
        'friday', 'saturday', 'sunday'
    ];

    function plural(count, word) {
        return count + ' ' + word + (count === 1 ? '' : 's');
    }

    function init() {
        var select = document.getElementById('id_class_days_per_week');

        if (!select) {
            return;
        }

        var boxes = DAY_FIELDS
            .map(function (name) { return document.getElementById('id_' + name); })
            .filter(Boolean);

        if (!boxes.length) {
            return;
        }

        // Live message shown under the weekday checkboxes.
        var hint = document.createElement('div');
        hint.className = 'class-days-hint';
        hint.setAttribute('aria-live', 'polite');

        var dayRow = boxes[0].closest('.form-row') || boxes[0].parentNode;
        dayRow.parentNode.insertBefore(hint, dayRow.nextSibling);

        function update() {
            var limit = parseInt(select.value, 10) || 0;
            var checked = boxes.filter(function (box) { return box.checked; }).length;

            boxes.forEach(function (box) {
                var disable = !box.checked && checked >= limit;
                box.disabled = disable;

                var wrapper = box.closest('.fieldBox') || box.parentNode;
                wrapper.classList.toggle('class-day-disabled', disable);
            });

            hint.classList.remove('is-ok', 'is-warning', 'is-error');

            if (checked === limit) {
                hint.textContent = checked + ' of ' + limit + ' days selected.';
                hint.classList.add('is-ok');
            } else if (checked < limit) {
                hint.textContent = 'Select ' + plural(limit - checked, 'more day') +
                    ' (' + checked + ' of ' + limit + ' selected).';
                hint.classList.add('is-warning');
            } else {
                hint.textContent = 'Too many days selected: untick ' +
                    plural(checked - limit, 'day') +
                    ' (' + checked + ' of ' + limit + ').';
                hint.classList.add('is-error');
            }
        }

        select.addEventListener('change', update);

        boxes.forEach(function (box) {
            box.addEventListener('change', update);
        });

        update();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
