import telebot
from foxford_test_task.app import models, database
from sqlalchemy.orm import Session
from datetime import datetime
from foxford_test_task.app import settings


bot = telebot.TeleBot(settings.token)


@bot.message_handler(commands=['start'])
def handle_start_help(message):
    user_name = message.from_user
    bot.send_message(message.from_user.id,
                     f"Привет, {user_name.first_name}! Опишите свою проблему и мы с вами свяжемся")


@bot.message_handler(content_types=['text'])
def get_text_messages(message):
    db: Session = database.SessionLocal()
    ticket = db.query(models.Tickets).filter(
        models.Tickets.applicant_name == message.from_user.first_name
    ).order_by(models.Tickets.id.desc()).first()
    if ticket:
        message_send = db.query(models.Tickets).filter(
            models.Tickets.id == ticket.id,
            models.Tickets.message_send != None
        ).order_by(models.Tickets.id.desc()).first()
    if message.text and (not ticket or ticket.status == 'Закрыт'):
        db_tickets = models.Tickets(
            applicant_name=message.from_user.first_name,
            applicant_id=message.from_user.id,
            text_ticket=message.text,
            date_create=datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        )
        db.add(db_tickets)
        db.commit()
        db.refresh(db_tickets)
        last_message = f"Спасибо за обращение, Ваше обращение зарегистрировано"
        bot.send_message(message.from_user.id, last_message)
    elif message_send and message_send.message_answer and ticket.status != 'Закрыт':
        nomer = bot.send_message(
            message.from_user.id, 'Дождитесь ответа от оператора или изменения статуса')
        bot.register_next_step_handler(nomer, get_text_messages)
    elif message_send and message_send.message_send and ticket.status != 'Закрыт':
        db.query(models.Tickets).filter(models.Tickets.applicant_id == message.from_user.id).update(
            {
                models.Tickets.message_answer: message.text
            },
            synchronize_session=False)
        db.commit()
        bot.send_message(message.from_user.id, 'Ждем ответа от оператора')
    elif not message_send:
        last_message = f"Вы уже делали обращение"
        bot.send_message(message.from_user.id, last_message)
    db.close()


bot.polling()
