from pydo.dbi import getConnection
import pydo as P
import config

def get_sequence_sql():
    return dict(sqlite='INTEGER PRIMARY KEY NOT NULL',
                sqlite2='INTEGER PRIMARY KEY NOT NULL',
                psycopg='SERIAL PRIMARY KEY',
                mysql='INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY')[config.DRIVER]


class Fixture(object):

    def setup(self):
        pass

    def cleanup(self):
        pass

    def run(self):
        pass

    def db():
        def fget(self):
            return getConnection('pydotest')
        return fget
    db=property(db())

    def __call__(self):
        self.setup()
        try:
           self.run ()
        finally:
           self.cleanup()
            


class base_fixture(Fixture):
    tables=dict(
        A="""CREATE TABLE a (
        id %(seqsql)s,
        name VARCHAR(96) UNIQUE NOT NULL,
        b_id INTEGER,
        ta VARCHAR(96) UNIQUE,
        tb VARCHAR(96),
        d INTEGER DEFAULT 33,
        w INTEGER,
        x INTEGER NOT NULL,
        y INTEGER NOT NULL,
        z INTEGER NOT NULL,
        UNIQUE(w, x),
        UNIQUE(y, z)
        )""",

        B="""CREATE TABLE b (
        id %(seqsql)s,
        x INTEGER
        )""",
        
        C="""CREATE TABLE c (
        id %(seqsql)s,
        x INTEGER)""",
        
        A_C="""CREATE TABLE a_c (
        a_id INTEGER NOT NULL,
        c_id INTEGER NOT NULL,
        PRIMARY KEY(a_id, c_id)
        )""",

        D="""CREATE TABLE d (
        id INTEGER NOT NULL PRIMARY KEY,
        x INTEGER
        )""",

        E="""CREATE TABLE e (
        id %(seqsql)s,
        user1 VARCHAR(128) NOT NULL,
        user2 VARCHAR(128) NOT NULL
        )""",

        F="""CREATE TABLE f (
        id %(seqsql)s,
        a_id INTEGER,
        c_id INTEGER
        )""")

    usetables=()
    useObjs=True
    guess=False

    def setup(self):
        c=self.db.cursor()
        d=dict(seqsql=get_sequence_sql())
        for table, cr in self.tables.items():
            if self.usetables and table not in self.usetables:
                continue
            cr %= d
            c.execute(cr)
            if self.useObjs:
                self.setupObj(table, self.guess)
        c.close()
        self.pre()


    def pre(self):
        pass

    def post(self):
        pass
    
    def setupObj(self, table, guess):
        if table=='A':
            class A(P.PyDO):
                connectionAlias='pydotest'
                if guess:
                    guess_columns=True
                else:
                    fields=(P.Sequence('id'),
                            P.Unique('name'),
                            'b_id',
                            'd',
                            'ta',
                            'tb',
                            'w',
                            'x',
                            'y',
                            'z')
                    unique=(('y', 'z'),)
                def getB(self):
                    return B.getUnique(id=self.b_id)

                def getC(self):
                    return self.joinTable('id', 'a_c', 'a_id', 'c_id', C, 'id')
                
                    
            self.A=A
        elif table=='B':
            class B(P.PyDO):
                connectionAlias='pydotest'
                if guess:
                    guess_columns=True
                else:
                    fields=(P.Sequence('id'),
                            'x')
                def getA(self):
                    return A.getSome(b_id=self.id)
                
            self.B=B
        elif table=='C':
            class C(P.PyDO):
                connectionAlias='pydotest'
                if guess:
                    guess_columns=True
                else:
                    fields=(P.Sequence('id'),
                            'x')
            self.C=C
        elif table=='A_C':
            class A_C(P.PyDO):
                connectionAlias='pydotest'
                if guess:
                    guess_columns=True
                else:
                    fields=('a_id', 'c_id')
                    unique=(('a_id', 'c_id'),)
            self.A_C=A_C
        elif table=='D':
            class D(P.PyDO):
                connectionAlias='pydotest'
                if guess:
                    guess_columns=True
                else:
                    fields=(P.Unique('id'),
                            'x')
            self.D=D
        elif table=='E':
            class E(P.PyDO):
                connectionAlias='pydotest'
                if guess:
                    guess_columns=True
                else:
                    fields=(P.Unique('id'),
                            'user1',
                            'user2')
            self.E=E

        elif table=='F':
            class F(P.PyDO):
                connectionAlias='pydotest'
                if guess:
                    guess_columns=True
                else:
                    fields=(P.Sequence('id'),
                            'a_id',
                            'c_id')
            self.F=F

    def cleanup(self):
        #
        # sqlite2 transactions won't rollback table creation; only data
        #
        if self.db.autocommit or config.DRIVER == "sqlite2":
            c=self.db.cursor()
            for table in self.tables:
                if self.usetables and table not in self.usetables:
                    continue
                c.execute('DROP TABLE %s' % table.lower())
            c.close()
        else:
            self.db.rollback()

        self.post()
