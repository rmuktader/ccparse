class TDParserError(Exception):
    pass

class BalanceMismatchError(TDParserError):
    pass

class DataIntegrityError(TDParserError):
    pass
