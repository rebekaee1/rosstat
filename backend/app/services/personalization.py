"""Стык почты с персональным выпуском (ADR-0032 ↔ ADR-0033): функции, которые вызывает почта.

* ``set_mail_personalization(db, user_id, enabled, request, source)`` — включить/выключить
  персональную подборку: журнал согласий ``mail_personal`` / ``mail_personal_revoked`` и аудит
  (ссылка «Письма без персональной подборки», ``api/mail.py``); коммит — у вызывающего;
* ``block_effect_summary(db, days)`` — эффект блоков по генераторам для вкладки «Почта» админ-BI;
* ``personal_off(db, user_id)`` — выключена ли подборка (последняя запись журнала).

Реализация — пакет ``app.services.newsletter_personal``.
"""
from app.services.newsletter_personal.metrics import block_effect_summary
from app.services.newsletter_personal.signals import personal_off, set_mail_personalization

__all__ = ["set_mail_personalization", "block_effect_summary", "personal_off"]
