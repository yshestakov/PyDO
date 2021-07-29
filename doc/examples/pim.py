"""
a small example PIM application, using sqlite.

The schema is actually rather ridiculous (why are contact -> notes
many to many?)  but you get the idea.

"""
import os
from mx.DateTime import now
from pydo import *

class Note(PyDO):
    connectionAlias="pim"
    # if created had a default value (which
    # it would if the version of sqlite this was
    # tested on supported anything like CURRENT_TIMESTAMP)
    # I'd set:
    # refetch=True
    fields=(Sequence('id'),
            'title',
            'body',
            'created')

class Address(PyDO):
    connectionAlias='pim'
    fields=(Sequence('id'),
            'line1',
            'line2',
            'town',
            'state',
            'country',
            'postal_code')

    def getContacts(self):
        return Contact.getSome(OR(EQ(FIELD('address_id1'), self.id),
                                  EQ(FIELD('address_id2'), self.id)))


class Contact(PyDO):
    connectionAlias='pim'
    fields=(Sequence('id'),
            'first_name',
            'last_name',
            'address_id1',
            'address_id2',
            'email1',
            'email2',
            'work_phone',
            'home_phone',
            'mobile_phone')

    Address1=ForeignKey('address_id1', 'id', Address)
    Address2=ForeignKey('address_id2', 'id', Address)

    def addNote(self, title, body):
        n=Note.new(title=title, body=body, created=now())
        junction=ContactNote.new(contact_id=self.id,
                                 note_id=n.id)

    getNotes=ManyToMany('id',
                        'contact_note',
                        'contact_id',
                        'note_id',
                        Note,
                        'id')


class ContactNote(PyDO):
    connectionAlias='pim'
    # table is specified here, because the class name
    # is not the same as the table name
    table="contact_note"
    fields=('contact_id',
            'note_id')
    unique=(('contact_id',
             'note_id'),)

DB=os.environ.get('PIMDB', 'pim.db')
initAlias('pim', 'sqlite', DB)

def initDB():
    joseAddress=Address.new(line1="43 Chestnut Place",
                            line2="Fourth Floor",
                            town="Princeton",
                            state="NJ",
                            country="USA",
                            postal_code="06540")
    jose=Contact.new(first_name='Jose',
                     last_name='Gutenberg',
                     email1='jgutenberg@example.com',
                     address_id1=joseAddress.id,
                     home_phone='609/555-1234')
    jose.addNote('French Tutor',
                 'meet every other Thursday at 7pm in the Annex')
    jose.commit()
    
                     
