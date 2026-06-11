import mesa


class HouseholdAgent(mesa.Agent):
    def __init__(self, unique_id, model):
        super().__init__(model)
        self.unique_id = unique_id

        # Balance sheet
        self.current_balance: float = 0.0  # deposits at bank (asset)
        self.current_debt: float = 0.0  # no liabilities
        self.equity: float = 0.0  # net worth

    def update_equity(self):
        self.equity = self.current_balance - self.current_debt

    def step(self):
        # The logic is orchestrated by the scheduler during the market clearing step
        pass
