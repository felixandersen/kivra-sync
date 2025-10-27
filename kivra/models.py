#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
This module contains GraphQL queries and data models for Kivra API.
"""

# GraphQL query for fetching receipts
RECEIPTS_QUERY = """
query Receipts($search: String, $limit: Int, $offset: Int) {
  receiptsV2(search: $search, limit: $limit, offset: $offset) {
    __typename
    total
    offset
    limit
    list {
      ...baseDetailsFields
    }
  }
}

fragment baseDetailsFields on ReceiptBaseDetails {
  __typename
  key
  purchaseDate
  totalAmount {
    formatted
  }
  attributes {
    isCopy
    isExpensed
    isReturn
    isTrashed
  }
  store {
    name
    logo {
      publicUrl
    }
  }
  attachments {
    id
    type
  }
  accessInfo {
    owner {
      isMe
      name
    }
  }
}
"""

# GraphQL query for fetching receipt details
RECEIPT_DETAILS_QUERY = """
query ReceiptDetails($key: String!) {
  receiptV2(key: $key) {
    key
    content {
      header {
        totalPurchaseAmount
        subAmounts
        isoDate
        formattedDate
        text
        labels {
          type
          text
        }
        logo {
          publicUrl
        }
      }
      footer {
        text
      }
      items {
        allItems {
          text
          items {
            text
            type
            ... on ProductListItem {
              ...productFields
            }
            ... on GeneralDepositListItem {
              money {
                formatted
              }
              isRefund
              description
              text
            }
            ... on GeneralDiscountListItem {
              money {
                formatted
              }
              isRefund
              text
            }
            ... on GeneralModifierListItem {
              money {
                formatted
              }
              isRefund
              text
            }
          }
        }
        noBonusItems {
          text
          items {
            type
            ... on ProductListItem {
              ...productFields
            }
          }
        }
        returnedItems {
          text
          items {
            type
            ... on ProductReturnListItem {
              name
              money {
                formatted
              }
              quantityCost {
                formatted
              }
              deposits {
                description
                money {
                  formatted
                }
                isRefund
              }
              costModifiers {
                description
                money {
                  formatted
                }
                isRefund
              }
              connectedReceipt {
                receiptKey
                description
                isParentReceipt
              }
              identifiers
              text
            }
          }
        }
      }
      storeInformation {
        text
        storeInformation {
          property
          value
          subRows {
            property
            value
          }
        }
      }
      paymentInformation {
        text
        totals {
          text
          totals {
            property
            value
            subRows {
              property
              value
            }
          }
        }
        paymentMethods {
          text
          methods {
            type
            information {
              property
              value
              subRows {
                property
                value
              }
            }
          }
        }
        customer {
          text
          customer {
            property
            value
            subRows {
              property
              value
            }
          }
        }
        cashRegister {
          text
          cashRegister {
            property
            value
            subRows {
              property
              value
            }
          }
        }
      }
    }
    campaigns {
      image {
        publicUrl
      }
      title
      key
      height
      width
      destinationUrl
    }
    sender {
      name
      key
    }
    attributes {
      isUpdatedWithReturns
    }
  }
}

fragment productFields on ProductListItem {
  name
  money {
    formatted
  }
  quantityCost {
    formatted
  }
  deposits {
    description
    money {
      formatted
    }
    isRefund
  }
  costModifiers {
    description
    money {
      formatted
    }
    isRefund
  }
  identifiers
  text
}
"""

# GraphQL query for fetching letters
LETTERS_QUERY = """
query ContentList($filter: ContentListFilter!, $senderKey: String, $take: Int!, $after: ID) {
  contents(
    filter: $filter
    senderKey: $senderKey
    take: $take
    after: $after
  ) {
    total
    existsMore
    list {
      ...ContentBaseDetails
    }
  }
}

fragment ContentBaseDetails on IContentBaseDetails {
  __typename
  key
  receivedAt
  attributes {
    isRead
    isTrashed
    isUpload
  }
  sender {
    key
    name
    iconUrl
  }
  subject
  accessInfo {
    owner {
      isMe
      name
    }
  }
}
"""

class KivraDocument:
    """Base class for Kivra documents (receipts and letters)."""
    
    def __init__(self, key, date, content_type=None):
        """
        Initialize a Kivra document.
        
        Args:
            key (str): Document key
            date (str): Document date
            content_type (str, optional): Content type
        """
        self.key = key
        self.date = date
        self.content_type = content_type
    
    def get_metadata(self):
        """
        Get document metadata.
        
        Returns:
            dict: Document metadata
        """
        raise NotImplementedError("Subclasses must implement get_metadata()")

class KivraReceipt(KivraDocument):
    """Class representing a Kivra receipt."""
    
    def __init__(self, key, date, store_name, data=None):
        """
        Initialize a Kivra receipt.
        
        Args:
            key (str): Receipt key
            date (str): Receipt date
            store_name (str): Store name
            data (dict, optional): Receipt data
        """
        super().__init__(key, date)
        self.store_name = store_name
        self.data = data
    
    def get_metadata(self, content_type='application/json'):
        """
        Get receipt metadata.
        
        Args:
            content_type (str): Content type
            
        Returns:
            dict: Receipt metadata
        """
        return {
            'type': 'receipt',
            'date': self.date,
            'store_name': self.store_name,
            'key': self.key,
            'content_type': content_type
        }

class KivraLetter(KivraDocument):
    """Class representing a Kivra letter."""
    
    def __init__(self, key, date, sender_name, data=None, part_index=None):
        """
        Initialize a Kivra letter.
        
        Args:
            key (str): Letter key
            date (str): Letter date
            sender_name (str): Sender name
            data (dict, optional): Letter data
            part_index (int, optional): Part index for multi-part letters
        """
        super().__init__(key, date)
        self.sender_name = sender_name
        self.data = data
        self.part_index = part_index
    
    def get_metadata(self, content_type='application/json'):
        """
        Get letter metadata.
        
        Args:
            content_type (str): Content type
            
        Returns:
            dict: Letter metadata
        """
        metadata = {
            'type': 'letter',
            'date': self.date,
            'sender_name': self.sender_name,
            'key': self.key,
            'content_type': content_type
        }
        
        if self.part_index is not None:
            metadata['part_index'] = self.part_index
            
        return metadata
