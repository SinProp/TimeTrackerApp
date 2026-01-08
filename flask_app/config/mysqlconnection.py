import pymysql.cursors
import os
from dbutils.pooled_db import PooledDB

# Module-level connection pool (singleton per database)
_pools = {}


def get_pool(db):
    """
    Get or create a connection pool for the specified database.
    Uses singleton pattern - only one pool per database name.
    """
    global _pools
    if db not in _pools:
        _pools[db] = PooledDB(
            creator=pymysql,
            maxconnections=10,  # Max pool size
            mincached=2,  # Min idle connections kept in pool
            maxcached=5,  # Max idle connections kept in pool
            blocking=True,  # Block when pool is exhausted (vs raising error)
            host=os.environ.get("MYSQL_HOST", "localhost"),
            user=os.environ.get("MYSQL_USER", "root"),
            password=os.environ.get("MYSQL_PASSWORD", ""),
            database=db,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )
    return _pools[db]


class MySQLConnection:
    def __init__(self, db):
        # Get a connection from the pool instead of creating a new one
        self.connection = get_pool(db).connection()

    def query_db(self, query, data=None):
        # This method will handle running all queries against the database.
        # 'query' is a string with placeholders for parameters.
        # 'data' is a dictionary or tuple of parameters to substitute into the query.
        with self.connection.cursor() as cursor:
            try:
                # Use mogrify to safely substitute parameters into the query.
                # After this, 'query' becomes a fully formed SQL statement with all parameters applied.
                query = cursor.mogrify(query, data)

                # mogrify returns bytes in PyMySQL, convert to string for consistent handling
                if isinstance(query, bytes):
                    query_str = query.decode("utf-8")
                else:
                    query_str = query

                print("Running Query:", query_str)

                # Now that the query is fully substituted, we can execute it directly without parameters.
                cursor.execute(query)

                # If the query is an INSERT, we return the last inserted ID.
                if query_str.lower().find("insert") >= 0:
                    self.connection.commit()
                    return cursor.lastrowid

                # If it's a SELECT, fetch all the results and return them as a list of dictionaries.
                elif query_str.lower().find("select") >= 0:
                    result = cursor.fetchall()
                    return result

                else:
                    # For UPDATE, DELETE, or other queries, we just commit the changes.
                    self.connection.commit()

            except Exception as e:
                # If something goes wrong (e.g., a syntax error in the query),
                # we print the error and return False.
                print("Something went wrong", e)
                return False

            finally:
                # Return the connection to the pool (not destroyed, just returned)
                self.connection.close()


def connectToMySQL(db):
    # This function returns an instance of MySQLConnection connected to the given database.
    return MySQLConnection(db)
