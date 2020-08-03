import random

class Router:
	def db_for_read(self , model , **hints):
		'''
		Reads are made from a randomly-chosen database.
		'''
		return random.choice(['default' , 'duplicate'])


	def db_for_write(self , model , **hints):
		'''
		All writes must be made to the base database.
		'''
		return 'default'


	def allow_relation(self , firstObj , secondObj , **hints):
		'''
		All databases are identical, therefore relations
		are always allowed.
		'''
		return True


	def allow_migrate(self , db , appLabel , modelName = None , **hints):
		'''
		Always allow migration (to the default database).
		'''
		return True
