import * as TabsPrimitive from '@radix-ui/react-tabs'

import { cn } from '../../lib/utils'

const Tabs = TabsPrimitive.Root

const TabsList = ({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) => (
  <TabsPrimitive.List className={cn('inline-flex h-10 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground', className)} {...props} />
)

const TabsTrigger = ({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) => (
  <TabsPrimitive.Trigger
    className={cn(
      'inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-all data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm',
      className,
    )}
    {...props}
  />
)

const TabsContent = ({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Content>) => (
  <TabsPrimitive.Content className={cn('mt-4 outline-none', className)} {...props} />
)

export { Tabs, TabsContent, TabsList, TabsTrigger }
