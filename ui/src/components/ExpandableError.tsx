import { useState } from 'react';
import { XCircleIcon, ChevronDownIcon, ChevronRightIcon } from '@heroicons/react/24/outline';

interface ExpandableErrorProps {
  title?: string;
  message: string;
  maxLength?: number;
}

export default function ExpandableError({
  title = "Error",
  message,
  maxLength = 200
}: ExpandableErrorProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const shouldTruncate = message.length > maxLength;
  const displayMessage = shouldTruncate && !isExpanded
    ? message.substring(0, maxLength) + '...'
    : message;

  return (
    <div className="rounded-md bg-red-50 p-4">
      <div className="flex">
        <XCircleIcon className="h-5 w-5 text-red-400 flex-shrink-0" />
        <div className="ml-3 flex-1 min-w-0">
          <h3 className="text-sm font-medium text-red-800">{title}</h3>
          <div className="mt-2">
            <div className="text-sm text-red-700 whitespace-pre-wrap break-words">
              {displayMessage}
            </div>
            {shouldTruncate && (
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="mt-2 inline-flex items-center text-sm text-red-800 hover:text-red-900 font-medium focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
              >
                {isExpanded ? (
                  <>
                    <ChevronDownIcon className="h-4 w-4 mr-1" />
                    Show less
                  </>
                ) : (
                  <>
                    <ChevronRightIcon className="h-4 w-4 mr-1" />
                    Show more ({message.length - maxLength} more characters)
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}