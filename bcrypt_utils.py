# Written by Jessica Dai, Sophie Lin, Nessa Tong, Ashley Yang (Olin)
# bcrypt_utils.py
import bcrypt

# Taken almost directly from bcrypt-demos in class!
def signup_hash(passwd, encoding='utf8'):
    '''Return a bcrypt-hashed password as a string, ready for DB storage.'''
    prior = bcrypt.gensalt()
    x = passwd.encode(encoding)
    y = bcrypt.hashpw(x, prior)
    return y.decode(encoding)

def verify_password(passwd, stored_hash, encoding='utf8'):
    '''Check if the entered password matches the stored bcrypt hash, given
    that the value stored in the databse is 'stored_hash'.'''
    stored_bytes = stored_hash.encode(encoding)
    passwd_bytes = passwd.encode(encoding)
    y = bcrypt.hashpw(passwd_bytes, stored_bytes)
    return stored_hash == y.decode(encoding)