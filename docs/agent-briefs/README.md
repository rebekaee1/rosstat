# Шаблоны заданий агентам

Какой шаблон для какой роли ([circle-playbook](../circle-playbook.md), раздел 4 «Как писать задания»):

| Роль | Шаблон |
|---|---|
| Наблюдатель на устройстве (проверка разрешений, «живой человек») | [viewport-tester-brief](viewport-tester-brief.md) |
| Критик «первый посетитель» на симуляторах, дизайн-круг | [visitor-brief](visitor-brief.md) |
| Скрытый оценщик критиков | [selector-brief](selector-brief.md) |
| Исполнитель зоны | [zone-brief](zone-brief.md) |
| Интеграция зон после слияния | [integration-brief](integration-brief.md) |
| Цикл знаний | [knowledge-sync-brief](knowledge-sync-brief.md) |
| Срочная починка по боевым объёмам | [hotfix-brief](hotfix-brief.md) |

Все субагенты запускаются на Sonnet (решение владельца 12.10.2026). Слова владельца исполнителям даются дословно, наблюдателям не даются. Ни в коммитах, ни в описаниях PR нет приписки `Co-Authored-By`.
