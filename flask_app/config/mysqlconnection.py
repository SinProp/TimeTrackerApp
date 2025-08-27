import pymysql.cursors


class MySQLConnection:
    def __init__(self, db):
        # This establishes a connection to the MySQL database using the provided credentials.
        # Make sure to adjust 'user', 'password', and 'host' as needed for your environment.
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='root',
            db=db,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )
        # Store the connection so we can use it in other methods.
        self.connection = connection

    def query_db(self, query, data=None):
        # This method will handle running all queries against the database.
        # 'query' is a string with placeholders for parameters.
        # 'data' is a dictionary or tuple of parameters to substitute into the query.
        with self.connection.cursor() as cursor:
            try:
                # Use mogrify to safely substitute parameters into the query.
                # After this, 'query' becomes a fully formed SQL statement with all parameters applied.
                query = cursor.mogrify(query, data)
                print("Running Query:", query)

                # Now that the query is fully substituted, we can execute it directly without parameters.
                cursor.execute(query)

                # If the query is an INSERT, we return the last inserted ID.
                if query.lower().find("insert") >= 0:
                    self.connection.commit()
                    return cursor.lastrowid

                # If it's a SELECT, fetch all the results and return them as a list of dictionaries.
                elif query.lower().find("select") >= 0:
                    result = cursor.fetchall()
                    return result

                else:
                    # For UPDATE, DELETE, or other queries, commit and return affected row count.
                    self.connection.commit()
                    return cursor.rowcount

            except Exception as e:
                # If something goes wrong (e.g., a syntax error in the query),
                # we print the error and return False.
                print("Something went wrong", e)
                return False

            finally:
                # Close the connection after each query. This ensures we don't hold onto resources longer than needed.
                self.connection.close()


def connectToMySQL(db):
    # This function returns an instance of MySQLConnection connected to the given database.
    return MySQLConnection(db)
